cdef extern from "common.h":
    pass

cdef extern from "vmath.h":
    ctypedef double fastf_t     # actually from bu.h, but vmath.h includes it
    ctypedef fastf_t point_t[3]
    ctypedef fastf_t vect_t[3]

cdef extern from "raytrace.h":
    struct rt_wdb:
        pass

    struct rt_db_internal:
        pass

    struct db_i:
        pass

cdef extern from "rtgeom.h":
    pass

cdef extern from "wdb.h":
    rt_wdb *wdb_fopen(char *filename)
    void wdb_close(rt_wdb *db)

    int mk_id(rt_wdb *db, char *name)
    int mk_id_units(rt_wdb *db, char *name, char *units)

    int mk_rpp(rt_wdb *db, char *name, point_t min_p, point_t max_p)
    int mk_sph(rt_wdb *db, char *name, point_t center, fastf_t radius)
    int mk_rcc(rt_wdb *db, char *name, point_t base, vect_t height,
        fastf_t radius)
    int mk_trc_h(rt_wdb *db, char *name, point_t base, vect_t height,
        fastf_t rad_base, fastf_t rad_top)
