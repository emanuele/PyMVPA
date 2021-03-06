# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:
### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ##
#
#   See COPYING file distributed along with the PyMVPA package for the
#   copyright and license terms.
#
### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ### ##
'''Tests for HDF5 converter'''

import numpy as np

from mvpa.testing import *
from mvpa.testing.datasets import datasets, saveload_warehouse

skip_if_no_external('h5py')
import h5py

import os
import tempfile

from mvpa.base.dataset import AttrDataset, save
from mvpa.base.hdf5 import h5save, h5load, obj2hdf, HDF5ConversionError
from mvpa.misc.data_generators import load_example_fmri_dataset
from mvpa.mappers.fx import mean_sample

class HDFDemo(object):
    pass

class CustomOldStyle:
    pass

def test_h5py_datasets():
    # this one stores and reloads all datasets in the warehouse
    rc_ds = saveload_warehouse()

    # global checks
    assert_equal(len(datasets), len(rc_ds))
    assert_equal(sorted(datasets.keys()), sorted(rc_ds.keys()))
    # check each one
    for d in datasets:
        ds = datasets[d]
        ds2 = rc_ds[d]
        assert_array_equal(ds.samples, ds2.samples)
        # we can check all sa and fa attrs
        for attr in ds.sa:
            assert_array_equal(ds.sa[attr].value, ds2.sa[attr].value)
        for attr in ds.fa:
            assert_array_equal(ds.fa[attr].value, ds2.fa[attr].value)
        # with datasets attributes it is more difficult, but we'll do some
        assert_equal(len(ds.a), len(ds2.a))
        assert_equal(sorted(ds.a.keys()), sorted(ds2.a.keys()))
        if 'mapper' in ds.a:
            # since we have no __equal__ do at least some comparison
            if __debug__:
                # debug mode needs special test as it enhances the repr output
                # with module info and id() appendix for objects
                assert_equal('#'.join(repr(ds.a.mapper).split('#')[:-1]),
                             '#'.join(repr(ds2.a.mapper).split('#')[:-1]))
            else:
                assert_equal(repr(ds.a.mapper), repr(ds2.a.mapper))


def test_h5py_dataset_typecheck():
    ds = datasets['uni2small']

    _, fpath = tempfile.mkstemp('mvpa', 'test')
    _, fpath2 = tempfile.mkstemp('mvpa', 'test')

    h5save(fpath2, [[1, 2, 3]])
    assert_raises(ValueError, AttrDataset.from_hdf5, fpath2)
    # this one just catches if there is such a group
    assert_raises(ValueError, AttrDataset.from_hdf5, fpath2, name='bogus')

    hdf = h5py.File(fpath, 'w')
    ds = AttrDataset([1, 2, 3])
    obj2hdf(hdf, ds, name='non-bogus')
    obj2hdf(hdf, [1, 2, 3], name='bogus')
    hdf.close()

    assert_raises(ValueError, AttrDataset.from_hdf5, fpath, name='bogus')
    ds_loaded = AttrDataset.from_hdf5(fpath, name='non-bogus')
    assert_array_equal(ds, ds_loaded)   # just to do smth useful with ds ;)

    # cleanup and ignore stupidity
    os.remove(fpath)
    os.remove(fpath2)


def test_matfile_v73_compat():
    mat = h5load(os.path.join(pymvpa_dataroot, 'v73.mat'))
    assert_equal(len(mat), 2)
    assert_equal(sorted(mat.keys()), ['x', 'y'])
    assert_array_equal(mat['x'], np.arange(6)[None].T)
    assert_array_equal(mat['y'], np.array([(1,0,1)], dtype='uint8').T)


def test_directaccess():
    f = tempfile.NamedTemporaryFile()
    h5save(f.name, 'test')
    assert_equal(h5load(f.name), 'test')
    f.close()
    f = tempfile.NamedTemporaryFile()
    h5save(f.name, datasets['uni4medium'])
    assert_array_equal(h5load(f.name).samples,
                       datasets['uni4medium'].samples)


def test_function_ptrs():
    if not externals.exists('nifti') and not externals.exists('nibabel'):
        raise SkipTest
    ds = load_example_fmri_dataset()
    # add a mapper with a function ptr inside
    ds = ds.get_mapped(mean_sample())
    f = tempfile.NamedTemporaryFile()
    h5save(f.name, ds)
    ds_loaded = h5load(f.name)
    fresh = load_example_fmri_dataset().O
    # check that the reconstruction function pointer in the FxMapper points
    # to the right one
    assert_array_equal(ds_loaded.a.mapper.forward(fresh),
                        ds.samples)

def test_0d_object_ndarray():
    f = tempfile.NamedTemporaryFile()
    a = np.array(0, dtype=object)
    h5save(f.name, a)
    a_ = h5load(f.name)
    ok_(a == a_)

def test_class_oldstyle():
    # AttributeError: CustomOld instance has no attribute '__reduce__'

    # old style classes do not define reduce -- sure thing we might
    # not need to support them at all, but then some meaningful
    # exception should be thrown
    co = CustomOldStyle()
    co.v = 1
    f = tempfile.NamedTemporaryFile()
    assert_raises(HDF5ConversionError, save, co, f.name, compression='gzip')

def test_locally_defined_class():
    # cannot store locally defined classes
    class Custom(object):
        pass
    c = Custom()
    f = tempfile.NamedTemporaryFile()
    assert_raises(HDF5ConversionError, h5save, f.name, c, compression='gzip')

def test_dataset_without_chunks():
    #  ValueError: All chunk dimensions must be positive (Invalid arguments to routine: Out of range)
    # MH: This is not about Dataset chunks, but about an empty samples array
    f = tempfile.NamedTemporaryFile()
    ds = AttrDataset([8], a=dict(custom=1))
    save(ds, f.name, compression='gzip')
    ds_loaded = h5load(f.name)
    ok_(ds_loaded.a.custom == ds.a.custom)

def test_recursion():
    obj = range(2)
    obj.append(HDFDemo())
    obj.append(obj)
    f = tempfile.NamedTemporaryFile()
    h5save(f.name, obj)
    lobj = h5load(f.name)
    assert_equal(obj[:2], lobj[:2])
    assert_equal(type(obj[2]), type(lobj[2]))
    ok_(obj[3] is obj)
    ok_(lobj[3] is lobj)
