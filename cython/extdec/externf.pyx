cdef extern from "math.h":
    cpdef double sin(double x)

cdef extern from "string.h":
    char *strstr(const char *haystack, const char *needle)

cdef char* data = "hfdsajflkjdlfkjlakdjf"
pos = strstr(needle='saj', haystack=data)
print pos != NULL
