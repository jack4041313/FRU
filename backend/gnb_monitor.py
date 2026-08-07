from backend.ognb_component.ognb_server import ognb


def start_gnb_monitor():
    ognb_ip = "10.255.174.135"

    gnb = ognb(
        ip_address=ognb_ip,
        username="ognb",
        password="ognb123"
    )

    gnb.connect()

    gnb.scan_throughput()
