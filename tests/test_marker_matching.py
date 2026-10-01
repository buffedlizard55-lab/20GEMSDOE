"""Synthetic operator checks, not empirical fault validation."""
import numpy as np
import pytest
from gems.marker_matching import paired_marker_displacement


def markers(shift_a=3,shift_b=3):
    y,x=np.indices((100,100))
    ya=y-shift_a*(x>=50)
    yb=y-shift_b*(x>=50)
    a=np.sin(2*np.pi*ya/13)+.25*np.cos(2*np.pi*ya/7)
    b=np.cos(2*np.pi*yb/13)+.25*np.sin(2*np.pi*yb/7)
    return a,b,np.ones(a.shape,bool)


def test_joint_offset_texture_beats_unshifted_marker():
    score,controls,meta=paired_marker_displacement(*markers())
    nooffset,_,_=paired_marker_displacement(*markers(0,0))
    assert score[30:70,49:51].mean()>.25
    assert nooffset.max()<1e-4
    assert score[:,0].max()==0 and score[0,:].max()==0
    assert meta["working_grid_cell_m"]==200
    assert (score>=0).all() and (score<=1).all()
    assert set(controls)=={"zero_lag_control","generic_dual_edge_control"}


def test_marker_conflict_is_attenuated_and_constant_texture_is_not_evidence():
    bad,_,_=paired_marker_displacement(*markers(3,-3))
    good,_,_=paired_marker_displacement(*markers(3,3))
    a,b,v=markers()
    flat,_,_=paired_marker_displacement(a,np.zeros_like(b),v)
    # Periodic textures can still create ambiguous matches; do not assert an
    # impossible guarantee that every contradictory marker response is zero.
    assert bad[30:70,49:51].mean()<.1*good[30:70,49:51].mean()
    assert flat.max()==0


def test_invalid_source_guard_excludes_holes_and_no_common_support():
    a,b,v=markers()
    a[49:52,49:52]=np.nan
    score,_,_=paired_marker_displacement(a,b,v)
    assert score[35:65,35:65].max()==0
    with pytest.raises(ValueError):
        paired_marker_displacement(a,b,np.zeros_like(v))
