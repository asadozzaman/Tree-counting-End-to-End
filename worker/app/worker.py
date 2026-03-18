import os
import time


def main() -> None:
    redis_url = os.getenv("REDIS_URL", "redis://redis:6379/0")
    print(f"worker started, waiting for queue at {redis_url}", flush=True)
    while True:
        time.sleep(10)
        print("worker heartbeat", flush=True)


if __name__ == "__main__":
    main()
