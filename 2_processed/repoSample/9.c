void black_target (const Edge& e, const Graph& g) const 
{
    BOOST_CHECK( color[target(e, g)] == Color::black() );


    typename boost::graph_traits<Graph>::adjacency_iterator ai, ai_end;
    for (boost::tie(ai, ai_end) = adjacent_vertices(target(e, g), g);
         ai != ai_end; ++ai)
      BOOST_CHECK( color[*ai] != Color::white() );
  }