void discover_vertex (const Vertex& u, const Graph&) const 
{
    BOOST_CHECK( get(color, u) == Color::gray() );
    if (u == src) {
      current_vertex = src;
    } else {
      BOOST_CHECK( parent[u] == current_vertex );
      BOOST_CHECK( distance[u] == current_distance + 1 );
      BOOST_CHECK( distance[u] == distance[parent[u]] + 1 );
    }
  }