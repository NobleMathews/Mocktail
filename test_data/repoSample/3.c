void examine_vertex (const Vertex& u, const Graph&) const 
{
    current_vertex = u;

    BOOST_CHECK( distance[u] == current_distance
                       || distance[u] == current_distance + 1 );
    if (distance[u] == current_distance + 1)
      ++current_distance;
  }