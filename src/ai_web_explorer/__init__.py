import argparse
import logging
import os

logging.basicConfig(level=logging.INFO)

parser = argparse.ArgumentParser(description="Explore a website")
parser.add_argument("domain", help="The domain to start the exploration from")
parser.add_argument(
    "--iterations",
    "-i",
    type=int,
    help="The number of iterations to explore",
    default=None,
)
parser.add_argument(
    "--store-titles",
    "-t",
    action="store_true",
    help="Store the titles of the webpages",
    default=False,
)

parser.add_argument(
    "--login",
    "-l",
    type=str,
    help="The username and password to use for login on the website separated by a colon",
    default=None,
)

parser.add_argument(
    "--additional-info",
    "-a",
    type=str,
    help="Additional information to be used for exploration",
    default="----- No additional information was provided -----",
)

parser.add_argument(
    "--output",
    "-o",
    type=str,
    help='Output format - "jsonsimple", "json" or "digraph". JSON is more detailed, digraph can be easily visualized',
    default="digraph",
)

parser.add_argument(
    "--restore",
    "-r",
    type=str,
    help="Restore the exploration from a file",
    default=None,
)


def main():
    import openai
    from dotenv import load_dotenv

    from . import loop
    from . import webstate

    load_dotenv()

    args = parser.parse_args()
    domain = args.domain
    url = f"http://{domain}"
    openai_client = openai.Client(
        api_key=os.getenv("OPENAI_API_KEY"),
        base_url=os.getenv("OPENAI_BASE_URL"),
    )

    logging.info(f"Exploring {domain}")
    
    # 冒号作分隔
    credentials = args.login.split(":") if args.login else [None, None]
    # 传递相关参数
    loop_config = loop.LoopConfig(
        iterations=args.iterations,
        store_titles=args.store_titles,
        confirm_titles=args.store_titles,
        username=credentials[0],
        password=credentials[1],
        additional_info=args.additional_info,
    )

    explore_loop = loop.ExploreLoop(domain, url, openai_client, loop_config)
    
    # 如果提供了恢复文件，则从文件中加载状态
    if args.restore:
        webstates = webstate.load_states_from_file(args.restore)
        explore_loop.set_webstates(webstates)

    explore_loop.start()

    if args.output == "jsonsimple":
        explore_loop.print_json(True)
    elif args.output == "json":
        explore_loop.print_json(False)
    elif args.output == "digraph":
        explore_loop.print_graph()
    explore_loop.stop()
