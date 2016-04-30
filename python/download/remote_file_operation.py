#!/usr/bin/python
# -*-coding:utf-8-*-

"""
Package the remote file download operation.
This package is based on paramiko.To get the latest stable release:
sudo pip install paramiko
Copyright(c) 2007-2015, by MY Capital Inc.
"""

from threading import Thread
from hashlib import sha1 as lsha1
from paramiko import AutoAddPolicy, SSHClient
import json
import os
import re


class Download(Thread):
    """
    a download thread which use ssh_client to fetch the remote file to
    specified path. after the download this thread exit automatically
    """
    def __init__(self, ssh_entity, dl_task_list, ret_map):
        self.ssh_client = ssh_entity                    # the local SSH entity
        self.dl_task_list = dl_task_list
        self.ret_map = ret_map
        Thread.__init__(self)

    def run(self):
        self.clt, self.sftp, err = self.ssh_client.ssh_connect()
        if not self.clt and not self.sftp:
            for task in self.dl_task_list:
                self.ret_map[task] = (-1, "ssh connect failed! %s" % err)
                return
        for task in self.dl_task_list:
            try:
                task_id = task[0]
                remote_file = task[1]
                local_file = task[2]
                # expand '~' in local file path
                local_file = re.sub('^~', os.path.expanduser("~"), local_file)
                if not self.parent_path_exists(local_file):
                    self.ret_map[task_id] = (-1, "no permission opt files")
                elif self.download(remote_file, local_file, task_id):
                    self.chmod(local_file, "644")
                    self.ret_map[task_id] = (0, "download success")
            except Exception, e:
                self.ret_map[task_id] = (-1, str(e))

    def parent_path_exists(self, local_file):
        ret = True
        p_path = os.path.dirname(local_file)
        if not os.path.exists(p_path):
            try:
                os.makedirs(p_path)
            except Exception:
                ret = False
        return ret

    def chmod(self, filename, mode):
        inner_mode = int(mode, 8)
        ret = True
        try:
            os.chmod(filename, inner_mode)
        except:
            ret = False
        return ret

    def download(self, remote_file, local_file, task_id, redo_cnt=3):
        checksum_cnt = redo_cnt
        while checksum_cnt:
            remote_checksum = self.remote_sha1sum(remote_file, task_id)
            if remote_checksum:
                break
            else:
                self.clt, self.sftp, err = self.ssh_client.ssh_connect()
                checksum_cnt -= 1

        # remote checksum failed
        if not remote_checksum:
            return False

        # checksum cmp before download
        local_checksum = self.local_sha1sum(local_file, task_id)
        if remote_checksum == local_checksum:
            return True
        else:
            download_cnt = redo_cnt
            download_ret = False
            while download_cnt:
                try:
                    self.sftp.get(remote_file, local_file)
                    download_ret = True
                    break
                except Exception as e:
                    self.ret_map[task_id] = (-1, "%s sftp.get failed %s" %
                                             (remote_file, str(e)))
                    self.clt, self.sftp, err = self.ssh_client.ssh_connect()
                    download_cnt -= 1
            if not download_ret:
                return False
        
        # checksum after download
        local_checksum = self.local_sha1sum(local_file, task_id)
        if remote_checksum != local_checksum:
            # delete the broken file
            self.local_delete(local_file)
            self.ret_map[task_id] = (-1, "download checksum diff error")
            return False
        else:
            return True

    def local_delete(self, local_file):
        try:
            os.remove(local_file)
        except OSError:
            pass

    def local_sha1sum(self, local_file, task_id):
        try:
            sha_handler = lsha1()
            with open(local_file, 'r') as open_file:
                for line in open_file:
                    sha_handler.update(line)
            return sha_handler.hexdigest()
        # except (OSError, IOError):
        except Exception, e:
            self.ret_map[task_id] = (-1, "local_sha1sum %s %s" %
                                     (local_file, str(e)))
            return None

    def remote_sha1sum(self, remote_file, task_id):
        try:
            out_info = self.clt.exec_command("sha1sum " + remote_file)[1]
            remote_sum = out_info.read()
            rf_checksum = remote_sum.split(' ')[0]
            if rf_checksum:
                return rf_checksum
            else:
                self.ret_map[task_id] = (-1, "remote file %s not exist" %
                                         remote_file)
                return None
        except Exception, e:
            self.ret_map[task_id] = (-1, "remote_sha1sum %s %s" %
                                     (remote_file, str(e)))
            return None


# TODO: add dis-connect check
class SSH(object):
    """package for ssh_client"""
    def __init__(self, host, user, password, port=22):
        self.host = host
        self.user = user
        self.password = password
        self.port = port

    def ssh_connect(self, reconn_cnt=2):
        clt = SSHClient()
        clt.load_system_host_keys()
        clt.set_missing_host_key_policy(AutoAddPolicy())
        connected = False
        while reconn_cnt > 0:
            try:
                clt.connect(hostname=self.host, username=self.user,
                            password=self.password, port=self.port)
                sftp = clt.open_sftp()
                connected = True
                break
            except Exception as e:
                errmsg = str(e)
                reconn_cnt -= 1
        if connected:
            return clt, sftp, None
        else:
            return None, None, errmsg

    def ssh_close(self, clt, sftp):
        if sftp:
            sftp.close()
        if clt:
            clt.close()
        
def task_deserialize(task_list, n_task_list):
    o_task_list = task_list["data"]
    remote_files = o_task_list["remote_files"]
    local_files = o_task_list["local_files"]
    tsk_size = min(len(remote_files), len(local_files))
    for i in range(tsk_size):
        tarr = []
        tarr.append(i)
        tarr.append(remote_files[i])
        tarr.append(local_files[i])
        n_task_list.append(tarr)


def dlret_serialize(dl_ret, task_list):
    ret = {}
    ret["seq"] = task_list["seq"]
    ret["type"] = task_list["type"]
    ret["return"] = 1
    ret["data"] = {"msg": [], "remote_file": []}
    for key, value in dl_ret.iteritems():
        if value[0] == -1:
            ret["return"] = -1
        # print key, value
        ret["data"]["msg"].append(value[1])
        ret["data"]["remote_file"].append(task_list["data"][
                                          "remote_files"][key])
    return json.dumps(ret)


def download_file(conn_cfg, o_task_list):
    tasks_per_thread = 3
    task_list = []
    ret_map = {}
    task_deserialize(o_task_list, task_list)
    task_nums = len(task_list)
    download_threads = -(-task_nums // tasks_per_thread)  # ceil division
    all_threads = []
    ssh_mgr = SSH(conn_cfg["host"], conn_cfg["user"],
                      conn_cfg["password"], conn_cfg["port"])
    for idx in range(download_threads):

        t_task_list = task_list[idx * tasks_per_thread:
                                (idx + 1) * tasks_per_thread]

        download_thread = Download(ssh_mgr, t_task_list, ret_map)
        download_thread.start()
        print id(ssh_mgr)
        all_threads.append(download_thread)

    for thread in all_threads:
        try:
            if thread.is_alive:
                thread.join()
        except:
            pass
    return ret_map


# __main__ function
def main(ser_cfg, dl_cmd):
    try:
        import sys
        reload(sys)
        sys.setdefaultencoding('utf8')
        connf_cfg = json.loads(ser_cfg)
        task_list = json.loads(dl_cmd)
        dl_ret = download_file(connf_cfg, task_list)
        ret = dlret_serialize(dl_ret, task_list)
        return ret
    except Exception:
        import logging
        logging.basicConfig(filename='example.log',level=logging.DEBUG)
        import traceback
        tv = traceback.format_exc()
        logging.debug(tv)
        return None
