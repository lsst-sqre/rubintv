import uvicorn


def run_rubintv() -> None:
    uvicorn.run("main:app", host="127.0.0.1", port=8000, log_level="info")


if __name__ == "__main__":
    run_rubintv()
