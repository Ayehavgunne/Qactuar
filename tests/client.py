import argparse
import threading
from time import time

import requests

RESPONSES = []
ELAPSEDES = []
THREADS = []
LOREM_IPSUM = """Lorem ipsum dolor sit amet, consectetur adipiscing elit. Nulla eu commodo justo. Interdum et malesuada fames ac ante ipsum primis in faucibus. Aliquam erat volutpat. Aliquam risus eros, mattis et volutpat eget, gravida vitae justo. Nunc risus leo, tincidunt in egestas vitae, dapibus sed enim. Interdum et malesuada fames ac ante ipsum primis in faucibus. Sed posuere libero vitae tortor mollis interdum sed quis risus. Phasellus sed turpis at augue luctus efficitur vitae vitae urna. Duis in lacus vitae tortor efficitur elementum a sed mauris. Morbi pharetra feugiat faucibus. Quisque risus dui, venenatis at placerat ut, dictum consequat lacus. Donec egestas hendrerit quam quis eleifend.

Nulla dictum blandit ligula, a interdum ipsum iaculis ut. Ut porta, orci sed ultricies tempor, felis metus sodales felis, at convallis urna nisi in arcu. Pellentesque quis condimentum dolor, in volutpat mauris. Donec sollicitudin tempus felis, non aliquam ante fringilla vel. Nulla suscipit rhoncus erat ac vehicula. Nullam lacinia sollicitudin suscipit. Nullam faucibus placerat sem ut pretium. Nunc at aliquet nulla. Duis vitae porta orci. Etiam consequat ipsum eu massa laoreet, et tincidunt lectus ultrices. Vivamus id iaculis libero, ac porttitor nunc. Integer faucibus nibh velit, ac bibendum ipsum lobortis id. Morbi ut consectetur sem.

Aliquam erat volutpat. Cras in vulputate nisl. Curabitur quis purus neque. Vivamus a faucibus arcu. Sed sit amet dignissim orci. Nulla at condimentum turpis, sed tristique tellus. Vestibulum dictum imperdiet nibh ut lacinia. Vestibulum scelerisque odio est, sed congue enim hendrerit quis. Quisque venenatis orci non venenatis pellentesque. Integer consectetur tristique lacus, at sagittis erat tincidunt eu. Nunc varius, lectus in consequat tincidunt, purus erat consectetur sem, ut aliquet tellus neque vitae purus. Sed ultricies massa id eleifend faucibus. Duis laoreet ac justo auctor porta. Nunc nec magna in sapien congue scelerisque. In velit dui, placerat ut quam nec, semper sagittis dui. Nam vel sem ultricies, iaculis justo mattis, ultricies felis.

Sed tempus vehicula rutrum. Morbi porta magna ut purus placerat vulputate. Phasellus efficitur dolor eget elit cursus congue. Quisque sagittis eget diam quis finibus. Praesent dignissim velit ac quam sagittis, ut rutrum lorem venenatis. Vivamus aliquet ex vitae ex ornare auctor. In hac habitasse platea dictumst.

Mauris nec est quis massa sollicitudin tempus eu et nisi. Nunc luctus lacus facilisis quam laoreet lacinia. Morbi sagittis ligula quis ligula ornare tempus vel vel neque. Vivamus porta scelerisque metus. Interdum et malesuada fames ac ante ipsum primis in faucibus. Morbi vitae blandit erat. Nullam nec iaculis dolor."""


def connect(num):
    response = requests.post(
        "http://localhost:8000/what", data={"thing": "stuff", "num": num}
    )
    elapsed = response.elapsed
    ELAPSEDES.append(elapsed.microseconds)
    response = response.text
    # RESPONSES.append(response)
    print(f"{response} {elapsed}")


def start(max_clients, max_conns):
    start_time = time()
    for client_num in range(max_clients):
        for connection_num in range(max_conns):
            t = threading.Thread(target=connect, args=(client_num,))
            t.daemon = True
            THREADS.append(t)
    for thread in THREADS:
        thread.start()
    for thread in THREADS:
        thread.join()
    for response in RESPONSES:
        print(response)
    end_time = time()
    total_time = end_time - start_time
    print(f"total time: {total_time}, avg: {(sum(ELAPSEDES)/len(ELAPSEDES))/1000} ms")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Test client for Qactuar.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--max-conns",
        type=int,
        default=1,
        help="Maximum number of connections per client.",
    )
    parser.add_argument(
        "--max-clients", type=int, default=1, help="Maximum number of clients."
    )
    args = parser.parse_args()
    start(args.max_clients, args.max_conns)
