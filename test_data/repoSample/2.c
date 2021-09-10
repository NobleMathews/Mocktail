void initialize_vertex (const Vertex& u, const Graph&) const 
{
    BOOST_CHECK(get(color, u) == Color::white());
  }