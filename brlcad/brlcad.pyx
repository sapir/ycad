cimport c_brlcad

import numpy as np
cimport numpy as np


class BrlcadError(StandardError):
    pass

cdef _check_res(int res):
    if res != 0:
        raise BrlcadError()

cdef np.ndarray[c_brlcad.fastf_t, ndim=1] _as_vec(lst):
    return np.array(lst, dtype='double')


cdef class RtInternal:
    cdef c_brlcad.rt_db_internal data

cdef class WDB:
    cdef c_brlcad.rt_wdb *ptr

    cpdef close(self):
        c_brlcad.wdb_close(self.ptr)

    def import_(self, bytes name, mat):
        inter = RtInternal()
        res = c_brlcad.wdb_import(self.ptr, &inter.data, name,
            <c_brlcad.mat_t> _as_vec(mat).data)
        _check_res(res)

    def put_internal(self, bytes name, RtInternal inter, double local2mm=1.0):
        res = c_brlcad.wdb_put_internal(self.ptr, name, &inter.data, local2mm)
        _check_res(res)

    def apply_mat(self, bytes name, mat):
        inter = self.import_(name, mat)
        self.put_internal(name, inter)

    def mk_id(self, bytes name, bytes unit_name=None):
        cdef int res

        if unit_name is None:
            res = c_brlcad.mk_id(self.ptr, name)
        else:
            res = c_brlcad.mk_id_units(self.ptr, name, unit_name)

        _check_res(res)
    
    def mk_rpp(self, bytes name, min_p, max_p):
        res = c_brlcad.mk_rpp(self.ptr, name,
            <c_brlcad.point_t> _as_vec(min_p).data,
            <c_brlcad.point_t> _as_vec(max_p).data)

        _check_res(res)

    def mk_sph(self, bytes name, center, radius):
        res = c_brlcad.mk_sph(self.ptr, name,
            <c_brlcad.point_t> _as_vec(center).data, radius)
        
        _check_res(res)

    def mk_rcc(self, bytes name, base, height, radius):
        res = c_brlcad.mk_rcc(self.ptr, name,
            <c_brlcad.point_t> _as_vec(base).data,
            <c_brlcad.vect_t> _as_vec(height).data,
            radius)

        _check_res(res)

    def mk_trc_h(self, bytes name, base, height, rad_base, rad_top):
        res = c_brlcad.mk_trc_h(self.ptr, name,
            <c_brlcad.point_t> _as_vec(base).data,
            <c_brlcad.vect_t> _as_vec(height).data,
            rad_base, rad_top)

        _check_res(res)

def wdb_fopen(filename):
    db = WDB()
    
    db.ptr = c_brlcad.wdb_fopen(filename)
    if db.ptr is NULL:
        raise BrlcadError()

    return db
