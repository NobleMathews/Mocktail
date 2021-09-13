void examine_edge (const Edge& e, const Graph& g) const 
{
    BOOST_CHECK( source(e, g) == current_vertex );
  }