cimport c_brlcad

import numpy as np
cimport numpy as np


class BrlcadError(StandardError):
    pass

cdef _check_res(int res):
    if res < 0:
        raise BrlcadError(res)

cdef np.ndarray[c_brlcad.fastf_t, ndim=1] _as_vec(lst):
    return np.array(lst, dtype='double')


def set_mat_deltas(np.ndarray mat, x, y, z):
    c_brlcad.MAT_DELTAS(<c_brlcad.mat_t> mat.data, x, y, z)

def set_mat_scale(np.ndarray mat, x, y, z):
    c_brlcad.MAT_SCALE(<c_brlcad.mat_t> mat.data, x, y, z)

def rotate_mat(np.ndarray mat, axis, angle):
    cdef axis_vec = _as_vec(axis)
    cdef axis_norm = np.linalg.norm(axis_vec)
    cdef np.ndarray[c_brlcad.fastf_t, ndim=1] unit_axis = axis_vec / axis_norm
    
    cdef np.ndarray[c_brlcad.fastf_t, ndim=1] origin = np.zeros(3)

    c_brlcad.bn_mat_arb_rot(
        <c_brlcad.mat_t> mat.data,
        <c_brlcad.point_t> origin.data,     # rotate about origin
        <c_brlcad.vect_t> unit_axis.data,
        angle)

cdef class RtInternal:
    cdef c_brlcad.rt_db_internal data

cdef class CombinationList:
    cdef c_brlcad.wmember wm_head

    UNION = c_brlcad.WMOP_UNION
    SUBTRACT = c_brlcad.WMOP_SUBTRACT
    INTERSECT = c_brlcad.WMOP_INTERSECT

    def __init__(self):
        c_brlcad.BU_LIST_INIT(&self.wm_head.l)

    def add_member(self, bytes name, op, np.ndarray mat=None):
        if mat is None:
            print 'no mat :('
            c_brlcad.mk_addmember(name, &self.wm_head.l, NULL, op)
        else:
            print 'got mat!', mat
            c_brlcad.mk_addmember(name, &self.wm_head.l,
                <c_brlcad.mat_t> mat.data, op)

cdef class WDB:
    cdef c_brlcad.rt_wdb *ptr

    cpdef close(self):
        c_brlcad.wdb_close(self.ptr)

    def import_(self, bytes name, np.ndarray mat):
        inter = RtInternal()
        res = c_brlcad.wdb_import(self.ptr, &inter.data, name,
            <c_brlcad.mat_t> mat.data)
        _check_res(res)
        return inter

    def put_internal(self, bytes name, RtInternal inter, double local2mm=1.0):
        res = c_brlcad.wdb_put_internal(self.ptr, name, &inter.data, local2mm)
        _check_res(res)

    def apply_mat(self, bytes name, np.ndarray mat):
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

    def mk_lfcomb(self, bytes name, CombinationList lst, is_region=True):
        res = c_brlcad.mk_lfcomb(self.ptr, name, &lst.wm_head, is_region)
        _check_res(res)

def wdb_fopen(filename):
    db = WDB()
    
    db.ptr = c_brlcad.wdb_fopen(filename)
    if db.ptr is NULL:
        raise BrlcadError()

    return db
