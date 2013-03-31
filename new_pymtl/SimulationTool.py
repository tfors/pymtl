#=========================================================================
# Simulation Tool
#=========================================================================
# Tool for simulating MTL models.
#
# This module contains classes which construct a simulator given a MTL model
# for execution in the python interpreter.

import pprint
import collections
import inspect

from Bits             import Bits
from connection_graph import Constant

# TODO: temporary
import ast_visitor
from ValueNode        import ValueNode
import warnings

#=========================================================================
# SimulationTool
#=========================================================================
# User visible class implementing a tool for simulating MTL models.
#
# This class takes a MTL model instance and creates a simulator for execution
# in the python interpreter.
class SimulationTool():

  #-----------------------------------------------------------------------
  # Constructor
  #-----------------------------------------------------------------------
  # Construct a simulator from a MTL model.
  def __init__( self, model ):

    # Check that the model has been elaborated
    if not model.is_elaborated():
      raise Exception( "cannot initialize {0} tool.\n"
                       "Provided model has not been elaborated yet!!!"
                       "".format( self.__class__.__name__ ) )

    self.model             = model
    self.nets              = []
    self.sequential_blocks = []
    self.event_queue       = collections.deque()
    self.vnode_callbacks   = collections.defaultdict(list)

    # Actually construct the simulator
    self._construct_sim()

  #-----------------------------------------------------------------------
  # Evaluate Combinational Blocks
  #-----------------------------------------------------------------------
  # Evaluates all events in the combinational logic event queue.
  def eval_combinational(self):
    while self.event_queue:
      func = self.event_queue.pop()
      #self.pstats.add_eval_call( func, self.num_cycles )
      func()

  #-----------------------------------------------------------------------
  # Add Callback to Event Queue
  #-----------------------------------------------------------------------
  # Add an event to the simulator event queue for later execution.
  #
  # This function will check if the written Node instance has any
  # registered events (functions decorated with @combinational), and if so, adds
  # them to the event queue.
  def add_event(self, value_node):
    # TODO: debug_event
    #print "    ADDEVENT: VALUE", value_node.__repr__(), value_node.value, value_node in self.vnode_callbacks
    if value_node in self.vnode_callbacks:
      funcs = self.vnode_callbacks[value_node]
      for func in funcs:
        if func not in self.event_queue:
          self.event_queue.appendleft(func)

  #-----------------------------------------------------------------------
  # Construct Simulator
  #-----------------------------------------------------------------------
  # Construct a simulator for the provided model.
  def _construct_sim(self):
    self._create_nets( self.model )
    self._insert_value_nodes()
    self._register_decorated_functions( self.model )

  #-----------------------------------------------------------------------
  # Create Nets
  #-----------------------------------------------------------------------
  # Generate nets describing structural connections in the model.  Each
  # net describes a set of Signal objects which have been interconnected,
  # either directly or indirectly, by calls to connect().
  def _create_nets( self, model ):

    # DEBUG
    #print 70*'-'
    #print "Model:", model
    #print "Ports:"
    #pprint.pprint( model.get_ports(), indent=3 )
    #print "Submodules:"
    #pprint.pprint( model.get_submodules(), indent=3 )

    #def a_printer( some_set ):
    #  return [ x.parent.name + '.' + x.name for x in some_set ]
    #t = [ a_printer( [ x.src_node, x.dest_node] ) for x in model.get_connections() ]
    #print "Connections:"
    #pprint.pprint( model.get_connections(), indent=3 )
    #pprint.pprint( t, indent=3 )

    # Utility function to collect all the Signal type objects (ports,
    # wires, constants) in the model.
    def collect_signals( model ):
      signals = set( model.get_ports() + model.get_wires() )
      for m in model.get_submodules():
        signals.update( collect_signals( m ) )
      return signals

    signals = collect_signals( model )

    # Utility function to filter only supported connections: ports, and
    # wires.  No slices or Constants.
    def valid_connection( c ):
      if c.src_slice or c.dest_slice:
        raise Exception( "Slices not supported yet!" )
      elif isinstance( c.src_node,  Constant ):
        return False
      elif isinstance( c.dest_node, Constant ):
        return False
      else:
        return True

    # Iterative Depth-First-Search algorithm, borrowed from Listing 5-5
    # in 'Python Algorithms': http://www.apress.com/9781430232377/
    def iter_dfs( s ):
      S, Q = set(), []
      Q.append( s )
      while Q:
        u = Q.pop()
        if u in S: continue
        S.add( u )
        connected_signals = [ x.other( u ) for x in u.connections
                              if valid_connection( x ) ]
        Q.extend( connected_signals )
        #yield u
      return S

    # Initially signals contains all the Signal type objects in the
    # model.  We perform a depth-first search on the connections of each
    # Signal object, and remove connected objects from the signals set.
    # The result is a collection of nets describing structural
    # connections in the design. Each independent net will later be
    # transformed into a single ValueNode object.
    while signals:
      s = signals.pop()
      net = iter_dfs( s )
      for i in net:
        #if i is not s:
        #  signals.remove( i )
        signals.discard( i )
      self.nets.append( net )

  #-----------------------------------------------------------------------
  # Insert Value Nodes into the Model
  #-----------------------------------------------------------------------
  # Transform each net into a single ValueNode object. Model attributes
  # currently referencing Signal objects will be modified to reference
  # the ValueNode object of their associated net instead.
  def _insert_value_nodes( self ):

    # DEBUG
    #print
    #print "NODE SETS"
    #for set in self.nets:
    #  print '    ', [ x.parent.name + '.' + x.name for x in set ]

    # Utility function which creates ValueNode callbacks.
    def create_notify_sim_closure( sim, vnode ):
      def notify_sim():
        sim.add_event( vnode )
      return notify_sim

    # Each grouping is a bits object, make all ports pointing to
    # it point to the Bits object instead
    for group in self.nets:
      # Get an element out of the set and use it to determine the bitwidth
      # of the net, needed to create a properly sized ValueNode object.
      # TODO: no peek() so have to pop() then reinsert it! Another way?
      # TODO: what about BitStructs?
      temp = group.pop()
      group.add( temp )
      vnode = Bits( temp.nbits )
      # Add a callback to the ValueNode so that the simulator is notified
      # whenever it's value changes.
      vnode.notify_sim = create_notify_sim_closure( self, vnode )
      # Modify model attributes currently referencing Signal objects to
      # reference ValueNode objects instead.
      for x in group:
        if 'IDX' in x.name:
          name, idx = x.name.split('IDX')
          x.parent.__dict__[ name ][ int (idx) ] = vnode
        elif isinstance( x, Constant ):
          vnode.write( x.value )
        else:
          x.parent.__dict__[ x.name ] = vnode

  #-----------------------------------------------------------------------
  # Register Decorated Functions
  #-----------------------------------------------------------------------
  # TODO: add comments
  def _register_decorated_functions( self, model ):

    # Add all cycle driven functions
    self.sequential_blocks.extend( model._tick_blocks )
    self.sequential_blocks.extend( model._posedge_clk_blocks )

    # TODO: this is getting pretty hacky...
    # TODO: should never use eval... but this is easy
    # TODO: how to handle when 's' isnt self
    # TODO: how to handle temps!
    def name_to_object( name ):
      s = model
      try:
        #HACKY, FIX
        if '[?]' in  name:
          list_name, rest = name.split('[?]')
          x = eval( list_name )
          assert isinstance( x, list )
          return x
        else:
          x = eval( name )
          if isinstance( x, ValueNode ):
            return x
          else:
            warnings.warn( "Cannot add variable '{}' to sensitivity list."
                           "".format( name ), Warning )
            return None
      except NameError:
        warnings.warn( "Cannot add variable '{}' to sensitivity list."
                       "".format( name ), Warning )
        return None


    # Get the sensitivity list of each event driven (combinational) block
    # TODO: do before or after we swap value nodes?
    for func in model._combinational_blocks:
      tree = ast_visitor.get_method_ast( func )
      loads, stores = ast_visitor.LeafVisitor().enter( tree )
      for x in loads:
        obj = name_to_object( x )
        print obj
        if isinstance( obj, list ):
          model._newsenses[ func ].extend( obj )
        elif isinstance( obj, ValueNode ):
          model._newsenses[ func ].append( obj )

    # Iterate through all @combinational decorated function names we detected,
    # retrieve their associated function pointer, then add entries for each
    # item in the function's sensitivity list to vnode_callbacks
    # TODO: merge this code with above to reduce memory, # of data structures?
    print "\nSENSES"
    for func_ptr, sensitivity_list in model._newsenses.items():
      print func_ptr, sensitivity_list
      for value_node in sensitivity_list:
        self.vnode_callbacks[ value_node ].append( func_ptr )
        # Prime the simulation by putting all events on the event_queue
        # This will make sure all nodes come out of reset in a consistent
        # state. TODO: put this in reset() instead?
        if func_ptr not in self.event_queue:
          self.event_queue.appendleft( func_ptr )

    # Recursively perform for submodules
    for m in model.get_submodules():
      self._register_decorated_functions( m )

