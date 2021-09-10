void tree_edge (const Edge& e, const Graph& g) const 
{
    BOOST_CHECK( get(color, target(e, g)) == Color::white() );
    Vertex u = source(e, g), v = target(e, g);
    BOOST_CHECK( distance[u] == current_distance );
    parent[v] = u;
    distance[v] = distance[u] + 1;
  }