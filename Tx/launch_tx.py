"""Keep transmitter errors visible in the console opened by the launcher."""

import traceback


def main() -> int:
    try:
        from run_transmitter import main as transmit
        transmit()
    except KeyboardInterrupt:
        return 0
    except Exception:
        traceback.print_exc()
        input("Press Enter to close TX...")
        return 1
    except SystemExit as exc:
        if exc.code in (None, 0):
            return 0
        print(exc)
        input("Press Enter to close TX...")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
