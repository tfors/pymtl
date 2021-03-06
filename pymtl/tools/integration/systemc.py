#=======================================================================
# systemc.py
#=======================================================================

from __future__ import print_function

import re
import os
import sys
import json
import hashlib
import inspect
import filecmp
import collections
from copy import deepcopy
from os.path import exists, basename
from shutil  import copyfile
from sc_helper import *

from ...model.metaclasses import MetaCollectArgs

from pymtl import *

class SystemCSourceFileError( Exception ): pass

class SomeMeta( MetaCollectArgs ):
  def __call__( self, *args, **kwargs ):
    inst = super( SomeMeta, self ).__call__( *args, **kwargs )
    
    # Get the full path of source folders based on the location of 
    # the python class and the relative path
    inst._auto_init()
    
    for i, x in enumerate(inst.sourcefolder):
      
      if x.startswith("/"):
        # already absolute path, pass
        pass
      else:
        # relative path, do concatenation
        x = os.path.dirname( inspect.getfile( inst.__class__ ) ) + os.sep + x
      
      if not x.endswith(os.sep):
        x += os.sep
      inst.sourcefolder[i] = x
    
    inst.vcd_file = '__dummy__'
    inst.elaborate()
    
    # Postpone port dict until elaboration.
    if not inst._port_dict:
      inst._port_dict = { port.name: port for port in inst.get_ports() }
    else:
      print(inst._port_dict)
    
    sc_module_name  = inst.__class__.__name__  
    model_name      = inst.class_name
    c_wrapper_file  = model_name + '_sc.cpp'
    py_wrapper_file = model_name + '_sc.py'
    lib_file        = 'lib{}_sc.so'.format( model_name )
    obj_dir         = 'obj_dir_' + model_name + os.sep
    
    if not exists( obj_dir ):
      os.mkdir( obj_dir )
    include_dirs     = deepcopy( inst.sourcefolder )
    include_dirs.append( obj_dir )
    
    # Copy all specified source file to obj folder for later compilation
    # Also try to copy header files by inferring the file extension
    # At the same time check caching status
    #
    # Check the combination of a path, a filename and a extension
    # for both the header and the source. According to C++ 
    # convention the header should have the same filename as the 
    # source file for the compiler to match.
    #
    # The reason why I split the source array and header array into 
    # two groups is for performance -- to hopefully reduce the number
    # of disk inode lookup and disk accesses by breaking the loop
    # when a header/source is found.
    
    uncached = {}
    src_ext  = {}
    tmp_objs = []
    
    hashfile = obj_dir + "/.hashdict"
    hashdict = {}
    if exists( hashfile ):
      with open( hashfile, "r" ) as f:
        hashdict = json.load( f )
    
    for path in inst.sourcefolder:
      for filename in inst.sourcefile:
        file_prefix = path    + filename
        temp_prefix = obj_dir + filename
        
        for group in [ [".h", ".hh", ".hpp", ".h++"  ],  # header group
                       [".cc", ".cpp", ".c++", ".cxx"] ]:# source group
          for ext in group: 
            target_file = file_prefix + ext
            temp_obj    = temp_prefix + ".o"
            
            if not exists( target_file ):
              # OK this is not the correct extension.
              continue
            
            tmp_objs.append( temp_obj )
            
            if ext.startswith(".c"):
              src_ext[temp_prefix] = ext
            
            # July 11, 2016
            # This piece of code copies all the files
            # for caching/tracking purpose.
            # Now I use SHA1 hash value to track the update of files,
            # so I comment out these lines.
            
            # temp_file = temp_prefix + ext
            
            # 1. No .o file, then yeah it hasn't been cached.
            # 2. No .c file, probably something unexpected happened.
            # 3. See if the cached file is not up to date.
            
            # if not exists( temp_obj ) or \
               # not exists( temp_file ) or \
               # not filecmp.cmp( temp_file, target_file ):
              
              # if exists( temp_obj ):
                # os.remove( temp_obj )
              # copyfile( target_file, temp_file )
              # uncached[temp_prefix] = target_file
            
            # 1. No .o file
            # 2. Not in the hash value dictionary
            # 3. Hash value match?
            
            def get_hash( filename ):
              with open( filename, "r" ) as f:
                return hashlib.sha1( f.read() ).hexdigest()
                
            h = get_hash( target_file )
              
            if not exists( temp_obj ) or \
               target_file not in hashdict or \
               h != hashdict[target_file]:
              uncached[temp_prefix] = file_prefix
              hashdict[target_file] = h
            
            break
    
    # This part is used to handle the missing of source file. 
    # Specifically, if the user specifies "foo" in s.sourcefile, but 
    # the above code is not able to find foo with every prefix in all
    # folders in s.sourcefolder, we have to terminate the compilation.
    
    unmatched = []
    for x in inst.sourcefile:
      matched = False
      for y in src_ext:
        if basename(y) == x:
          matched = True
          break
      if not matched:
        unmatched.append( "\""+ x + "\"" )
    
    if unmatched:
      raise SystemCSourceFileError( '\n'
        '-   Source file for [{}] not found.\n'
        '-   Please double check s.sourcefolder and s.sourcefile!'\
          .format(", ".join( unmatched )) )
    
    # Remake only if there're uncached files

    if not uncached:
      # print( "All Cached!")
      pass
    else:
      # print( "Not Cached", uncached )
      
      # Dump new hashdict
      with open( hashfile, "w" ) as f:
        json.dump( hashdict, f )
      
      # Compile all uncached modules to .o object file
      for obj, src in uncached.items():
        compile_object( obj, src + src_ext[obj], include_dirs )
    
    # Regenerate the shared library .so file if individual modules are 
    # updated or the .so file is missing.
    
    if uncached or not exists( lib_file ):
      
      # Use list for tmp_objs and all_objs to keep dependecies 
      # O(n^2) but maybe we could refine it later when we need to deal 
      # with thousands of files ...
      
      all_objs = []
      for o in tmp_objs:
        if o not in all_objs:
          all_objs.append(o)
      
      systemc_to_pymtl( inst, # model instance
                        obj_dir, include_dirs, sc_module_name,
                        all_objs, c_wrapper_file, lib_file, # c wrapper
                        py_wrapper_file # py wrapper
                      )
    
    # Follows are the same as Translation Tool
    
    # Use some trickery to import the compiled version of the model
    sys.path.append( os.getcwd() )
    __import__( py_wrapper_file[:-3] )
    imported_module = sys.modules[ py_wrapper_file[:-3] ]

    # Get the model class from the module, instantiate and elaborate it
    model_class = imported_module.__dict__[ model_name ]
    
    new_inst  = model_class()
    new_inst.vcd_file = None

    new_inst.__class__.__name__  = inst.__class__.__name__
    new_inst.__class__.__bases__ = (SystemCModel,)
    new_inst._args        = inst._args
    new_inst.modulename   = inst.modulename
    new_inst.sourcefile   = inst.sourcefile
    new_inst.sourcefolder = inst.sourcefolder
    new_inst.sclinetrace  = inst.sclinetrace
    new_inst._param_dict  = inst._param_dict
    new_inst._port_dict   = inst._port_dict

    # TODO: THIS IS SUPER HACKY. FIXME
    # This copies the user-defined line_trace method from the
    # VerilogModel to the generated Python wrapper.
    try:
      new_inst.__class__.line_trace = inst.__class__.__dict__['line_trace']

      # If we make it here this means the user has set Verilog line
      # tracing to true, but has _also_ defined a PyMTL line tracing, but
      # you can't have both.

      if inst.sclinetrace:
        raise SystemCImportError( "Cannot define a PyMTL line_trace\n"
          "function and also use sclinetrace = True. Must use _either_\n"
          "PyMTL line tracing or use Verilog line tracing." )

    except KeyError:
      pass

    return new_inst

#-----------------------------------------------------------------------
# SystemCModel
#-----------------------------------------------------------------------

class SystemCModel( Model ):
  """
  A PyMTL model for importing hand-written SystemC modules.

  Attributes:
    modulename   Name of the Verilog module to import.
    sourcefile   List of C++ source files to be compiled
    sourcefolder List of folders which contain source files
    
  """
  __metaclass__ = SomeMeta

  modulename   = None
  sourcefile   = None
  sourcefolder = None
  sclinetrace  = False

  _param_dict  = None
  _port_dict   = None

  # set_params: Currently no support for parametrizing SystemC module

  #---------------------------------------------------------------------
  # set_ports
  #---------------------------------------------------------------------
  def set_ports( self, port_dict ):
    """Specify values for each parameter in the imported SystemC module.

    Note that port_dict should be a dictionary that provides a mapping
    from port names (strings) to PyMTL InPort or OutPort objects, for
    examples:

    >>> s.set_ports({
    >>>   'clk':    s.clk,
    >>>   'reset':  s.reset,
    >>>   'input':  s.in_,
    >>>   'output': s.out,
    >>> })
    """

    self._port_dict = collections.OrderedDict( sorted(port_dict.items()) )

  #---------------------------------------------------------------------
  # _auto_init
  #---------------------------------------------------------------------
  def _auto_init( self ):
    """Infer fields not set by user based on Model attributes."""

    if not self.modulename:
      self.modulename = self.__class__.__name__

    if not self.sourcefile:
      file_ = inspect.getfile( self.__class__ )
      self.sourcefile = [ self.modulename ]
      
    # If the sourcefolder is not defined then define it as the same
    # path as the python file, otherwise just by default append 
    # the python file path to s.sourcefolder
    
    file_ = inspect.getfile( self.__class__ )
    if not self.sourcefolder:
      self.sourcefolder = [ os.path.dirname( file_ ) ]
    else:
      self.sourcefolder.append( os.path.dirname( file_ ) )

    if not self._param_dict:
      self._param_dict = self._args

