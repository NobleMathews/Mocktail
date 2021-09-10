void non_tree_edge (const Edge& e, const Graph& g) const 
{
    BOOST_CHECK( color[target(e, g)] != Color::white() );

    if (boost::is_directed(g))

      BOOST_CHECK(distance[target(e, g)] <= distance[source(e, g)] + 1);
    else {

      BOOST_CHECK(distance[target(e, g)] == distance[source(e, g)]
                        || distance[target(e, g)] == distance[source(e, g)] + 1
                        || distance[target(e, g)] == distance[source(e, g)] - 1
                        );
    }
  }