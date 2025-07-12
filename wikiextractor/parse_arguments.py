import os ,argparse,sys
from multiprocessing import cpu_count
from .constents import __version__ 
def parse_arguments():
	parser = argparse.ArgumentParser(prog=os.path.basename(sys.argv[0]),
									 formatter_class=argparse.RawDescriptionHelpFormatter,
									 description=__doc__)
	parser.add_argument("input",
						help="XML wiki dump file")
	groupO = parser.add_argument_group('Output')
	groupO.add_argument("-o", "--output", default="text",
						help="directory for extracted files (or '-' for dumping to stdout)")
	groupO.add_argument("-b", "--bytes", default="1M",
						help="maximum bytes per output file (default %(default)s); 0 means to put a single article per file",
						metavar="n[KMG]")
	groupO.add_argument("-c", "--compress", action="store_true",
						help="compress output files using bzip")
	groupO.add_argument("--json", action="store_true",
						help="write output in json format instead of the default <doc> format")

	groupP = parser.add_argument_group('Processing')
	groupP.add_argument("--html", action="store_true",
						help="produce HTML output, subsumes --links")
	groupP.add_argument("-l", "--links", action="store_true",
						help="preserve links")
	groupP.add_argument("-ns", "--namespaces", default="", metavar="ns1,ns2",
						help="accepted namespaces")
	groupP.add_argument("--templates",
						help="use or create file containing templates")
	groupP.add_argument("--no-templates", action="store_true",
						help="Do not expand templates")
	groupP.add_argument("--html-safe", default=True,
						help="use to produce HTML safe output within <doc>...</doc>")
	default_process_count = cpu_count() - 1
	parser.add_argument("--processes", type=int, default=default_process_count,
						help="Number of processes to use (default %(default)s)")

	groupS = parser.add_argument_group('Special')
	groupS.add_argument("-q", "--quiet", action="store_true",
						help="suppress reporting progress info")
	groupS.add_argument("--debug", action="store_true",
						help="print debug info")
	groupS.add_argument("-a", "--article", action="store_true",
						help="analyze a file containing a single article (debug option)")
	groupS.add_argument("-v", "--version", action="version",
						version='%(prog)s ' + __version__,
						help="print program version")

	args = parser.parse_args()
	return args
