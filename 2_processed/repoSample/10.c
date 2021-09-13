void finish_vertex (const Vertex& u, const Graph&) const 
{
    BOOST_CHECK( color[u] == Color::black() );

  }