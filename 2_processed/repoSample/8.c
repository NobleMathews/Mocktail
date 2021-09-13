void gray_target (const Edge& e, const Graph& g) const 
{
    BOOST_CHECK( color[target(e, g)] == Color::gray() );
  }