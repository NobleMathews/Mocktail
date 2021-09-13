int test_main (int argc, char* argv[]) 
{
  using namespace boost;
  int max_V = 7;
  if (argc > 1)
    max_V = atoi(argv[1]);

  bfs_test< adjacency_list<vecS, vecS, directedS> >::go(max_V);
  bfs_test< adjacency_list<vecS, vecS, undirectedS> >::go(max_V);
  return 0;
}