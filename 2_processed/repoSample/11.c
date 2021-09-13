static void go (vertices_size_type max_V) 
{
    typedef typename Traits::vertex_descriptor vertex_descriptor;
    typedef boost::color_traits<boost::default_color_type> Color;

    vertices_size_type i;
    typename Traits::edges_size_type j;
    typename Traits::vertex_iterator ui, ui_end;

    boost::mt19937 gen;

    for (i = 0; i < max_V; ++i)
      for (j = 0; j < i*i; ++j) {
        Graph g;
        boost::generate_random_graph(g, i, j, gen);


        vertex_descriptor start = boost::random_vertex(g, gen);


        std::vector<int> distance(i, (std::numeric_limits<int>::max)());
        distance[start] = 0;
        std::vector<vertex_descriptor> parent(i);
        for (boost::tie(ui, ui_end) = vertices(g); ui != ui_end; ++ui)
          parent[*ui] = *ui;
        std::vector<boost::default_color_type> color(i);


        typedef typename boost::property_map<Graph, boost::vertex_index_t>::const_type idx_type;
        idx_type idx = get(boost::vertex_index, g);


        typedef
          boost::iterator_property_map<std::vector<int>::iterator, idx_type>
          distance_pm_type;
        distance_pm_type distance_pm(distance.begin(), idx);
        typedef
          boost::iterator_property_map<typename std::vector<vertex_descriptor>::iterator, idx_type>
          parent_pm_type;
        parent_pm_type parent_pm(parent.begin(), idx);
        typedef
          boost::iterator_property_map<std::vector<boost::default_color_type>::iterator, idx_type>
          color_pm_type;
        color_pm_type color_pm(color.begin(), idx);


        bfs_testing_visitor<distance_pm_type, parent_pm_type, Graph,
          color_pm_type>
          vis(start, distance_pm, parent_pm, color_pm);

        boost::breadth_first_search(g, start,
                                    visitor(vis).
                                    color_map(color_pm));


        for (boost::tie(ui, ui_end) = vertices(g); ui != ui_end; ++ui)
          if (color[*ui] == Color::white()) {
            std::vector<boost::default_color_type> color2(i, Color::white());
            BOOST_CHECK(!boost::is_reachable(start, *ui, g, color_pm_type(color2.begin(), idx)));
          }



        for (boost::tie(ui, ui_end) = vertices(g); ui != ui_end; ++ui)
          if (parent[*ui] != *ui)
            BOOST_CHECK(distance[*ui] == distance[parent[*ui]] + 1);
      }
  }