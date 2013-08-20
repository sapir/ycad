from libc.stdint cimport uint32_t

cdef extern from "common.h":
    pass

cdef extern from "vmath.h":
    ctypedef double fastf_t     # actually from bu.h, but vmath.h includes it
    ctypedef fastf_t point_t[3]
    ctypedef fastf_t vect_t[3]
    ctypedef fastf_t mat_t[4*4]

    void MAT_ZERO(mat_t mat)
    void MAT_IDN(mat_t mat)
    void MAT_DELTAS(mat_t mat, fastf_t x, fastf_t y, fastf_t z)
    void MAT_DELTAS_VEC(mat_t mat, vect_t vec)
    void MAT_SCALE(mat_t mat, fastf_t x, fastf_t y, fastf_t z)
    void MAT_SCALE_VEC(mat_t mat, vect_t vec)
    void MAT_SCALE_ALL(mat_t mat, fastf_t value)

cdef extern from "raytrace.h":
    struct rt_wdb:
        pass

    struct rt_db_internal:
        pass

    struct db_i:
        pass

cdef extern from "rtgeom.h":
    pass

cdef extern from "bu.h":
    struct bu_list:
        uint32_t magic
        bu_list *forw
        bu_list *back

    void BU_LIST_INIT(bu_list *_hp)

cdef extern from "wdb.h":
    struct wmember:
        bu_list l
        int wm_op
        mat_t wm_mat
        char *wm_name

    # values for wm_op. they're actually macro constants.
    char WMOP_INTERSECT
    char WMOP_SUBTRACT
    char WMOP_UNION


    rt_wdb *wdb_fopen(char *filename)
    void wdb_close(rt_wdb *db)
    
    int wdb_import(rt_wdb *db, rt_db_internal *inter, char *name, mat_t mat)
    int wdb_put_internal(rt_wdb *db, const char *name, rt_db_internal *inter,
        double local2mm)

    int mk_id(rt_wdb *db, char *name)
    int mk_id_units(rt_wdb *db, char *name, char *units)

    int mk_rpp(rt_wdb *db, char *name, point_t min_p, point_t max_p)
    int mk_sph(rt_wdb *db, char *name, point_t center, fastf_t radius)
    int mk_rcc(rt_wdb *db, char *name, point_t base, vect_t height,
        fastf_t radius)
    int mk_trc_h(rt_wdb *db, char *name, point_t base, vect_t height,
        fastf_t rad_base, fastf_t rad_top)
    
    wmember *mk_addmember(char *name, bu_list *headp, mat_t mat, int op)

    int mk_lcomb(rt_wdb *db, char *name, wmember *headp, int is_region,
        char *shadername, char *shaderargs, unsigned char rgb[3], int inherit)
    int mk_lfcomb(rt_wdb *db, char *name, wmember *headp, int is_region)
