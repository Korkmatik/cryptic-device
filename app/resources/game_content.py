import math
from typing import Tuple, List

from app import m, wrapper
from models.hardware import Hardware
from models.service import Service
from models.workload import Workload
from vars import hardware, resolve_ram_type, resolve_gpu_type


def check_exists(user: str, elements: dict) -> Tuple[bool, dict]:
    response: dict = m.contact_microservice("inventory", ["inventory", "list"], {"owner": user})

    names: List[str] = [x["element_name"] for x in response["elements"]]

    if elements["cpu"] not in names:
        return False, {"error": "you_dont_own_such_cpu"}
    if elements["motherboard"] not in names:
        return False, {"error": "you_dont_own_such_motherboard"}
    if elements["gpu"] not in names:
        return False, {"error": "you_dont_own_such_gpu"}
    for ram in elements["ram"]:
        if ram not in names:
            return False, {"error": "you_dont_own_such_ram"}
        else:
            names.remove(ram)
    for disk in elements["disk"]:
        if disk not in names:
            return False, {"error": "you_dont_own_such_disk"}
        else:
            names.remove(disk)

    return True, {}


def delete_items(user: str, elements: dict):
    m.contact_microservice("inventory", ["inventory", "delete_by_name"], {"owner": user, "item_name": elements["cpu"]})
    m.contact_microservice(
        "inventory", ["inventory", "delete_by_name"], {"owner": user, "item_name": elements["motherboard"]}
    )
    m.contact_microservice("inventory", ["inventory", "delete_by_name"], {"owner": user, "item_name": elements["gpu"]})
    for ram in elements["ram"]:
        m.contact_microservice("inventory", ["inventory", "delete_by_name"], {"owner": user, "item_name": ram})
    for disk in elements["disk"]:
        m.contact_microservice("inventory", ["inventory", "delete_by_name"], {"owner": user, "item_name": disk})


def check_element_existence(elements: dict) -> Tuple[bool, dict]:
    if elements["cpu"] not in hardware["cpu"]:
        return False, {"error": "element_cpu_not_found"}
    if elements["gpu"] not in hardware["gpu"]:
        return False, {"error": "element_gpu_not_found"}
    if elements["motherboard"] not in hardware["mainboards"]:
        return False, {"error": "element_motherboard_not_found"}
    for disk in elements["disk"]:
        if disk not in hardware["disk"]:
            return False, {"error": "element_disk_not_found"}
    for ram in elements["ram"]:
        if ram not in hardware["ram"]:
            return False, {"error": "element_ram_not_found"}

    return True, {}


def check_compatible(elements: dict) -> Tuple[bool, dict]:
    exists, message = check_element_existence(elements)
    if not exists:
        return False, message

    cpu: str = elements["cpu"]
    motherboard: str = elements["motherboard"]
    ram: List[str] = elements["ram"]
    # gpu: str = elements["gpu"] ask gamedesign
    disk: List[str] = elements["disk"]

    if hardware["cpu"][cpu]["sockel"] != hardware["mainboards"][motherboard]["sockel"]:
        return False, {"error": "cpu_and_mainboard_sockel_do_not_fit"}

    if hardware["mainboards"][motherboard]["ram"]["ramSlots"] < len(ram):
        return False, {"error": "mainboard_has_not_this_many_ram_slots"}

    for ram_stick in ram:
        if hardware["ram"][ram_stick]["ramTyp"] != hardware["mainboards"][motherboard]["ram"]["typ"]:
            return False, {"error": "ram_type_does_not_fit_what_you_have_on_your_mainboard"}

    for i in disk:
        if hardware["disk"][i]["interface"] != hardware["mainboards"][motherboard]["diskStorage"]["interface"]:
            return False, {"error": "your_hard_drive_interface_does_not_fit_with_the_motherboards_one"}

    if len(ram) < 1:
        return False, {"error": "you_need_at_least_one_ramstick"}
    if len(disk) < 1:
        return False, {"error": "you_need_at_least_one_harddrive"}

    return True, {}


def calculate_power(elements: dict) -> Tuple[float, float, float, float, float]:
    cpu: str = elements["cpu"]
    motherboard: str = elements["motherboard"]
    ram: List[str] = elements["ram"]
    gpu: str = elements["gpu"]
    disk: List[str] = elements["disk"]

    performance_cpu: float = hardware["cpu"][cpu]["cores"] * hardware["cpu"][cpu]["frequencyMax"]

    performance_ram: float = 0
    for ram_stick in ram:
        performance_ram += (
            min(
                resolve_ram_type[hardware["mainboards"][motherboard]["ram"]["typ"]],
                resolve_ram_type[hardware["ram"][ram_stick]["ramTyp"]],
            )
            * hardware["ram"][ram_stick]["ramSize"]
        )

    performance_gpu: float = resolve_gpu_type[hardware["gpu"][gpu]["interface"]] * math.sqrt(
        hardware["gpu"][gpu]["ramSize"] * hardware["gpu"][gpu]["frequency"]
    )

    disk_storage: float = 0

    for i in disk:
        disk_storage += hardware["disk"][i]["capacity"] * math.log1p(
            hardware["disk"][i]["writingSpeed"] * hardware["disk"][i]["readingSpeed"]
        )

    network: float = hardware["mainboards"][motherboard]["networkCard"]["speed"]

    return performance_cpu, performance_ram, performance_gpu, disk_storage, network


def create_hardware(elements: dict, device_uuid: str) -> None:
    Hardware.create(device_uuid, elements["cpu"], "cpu")
    Hardware.create(device_uuid, elements["gpu"], "gpu")
    Hardware.create(device_uuid, elements["motherboard"], "mainboard")
    for disk in elements["disk"]:
        Hardware.create(device_uuid, disk, "disk")
    for ram in elements["ram"]:
        Hardware.create(device_uuid, ram, "ram")


def scale_resources(s: List[Service], scale: Tuple[float, float, float, float, float]):
    for service in s:
        send: dict = {
            "service_uuid": service.service_uuid,
            "cpu": scale[0] * service.allocated_cpu,
            "ram": scale[1] * service.allocated_ram,
            "gpu": scale[2] * service.allocated_gpu,
            "disk": scale[3] * service.allocated_disk,
            "network": scale[4] * service.allocated_network,
        }

        m.contact_microservice("service", ["hardware", "scale"], send)


def generate_scale(
    data: Tuple[float, float, float, float, float], wl: Workload
) -> Tuple[float, float, float, float, float]:
    return (
        min(wl.performance_cpu / (wl.usage_cpu + data[0]), 1),
        min(wl.performance_ram / (wl.usage_ram + data[1]), 1),
        min(wl.performance_gpu / (wl.usage_gpu + data[2]), 1),
        min(wl.performance_disk / (wl.usage_disk + data[3]), 1),
        min(wl.performance_network / (wl.usage_network + data[4]), 1),
    )


def dict2tuple(data: dict) -> Tuple[float, float, float, float, float]:
    return data["cpu"], data["ram"], data["gpu"], data["disk"], data["network"]


def turn(data: Tuple[float, float, float, float, float]) -> Tuple[float, float, float, float, float]:
    return -1 * data[0], -1 * data[1], -1 * data[2], -1 * data[3], -1 * data[4]


def stop_all_service(device_uuid: str, delete: bool = False) -> None:
    for obj in wrapper.session.query(Service).filter_by(device_uuid=device_uuid).all():
        wrapper.session.delete(obj)
    wl: Workload = wrapper.session.query(Workload).get(device_uuid)
    wl.usage_cpu = 0
    wl.usage_ram = 0
    wl.usage_gpu = 0
    wl.usage_disk = 0
    wl.usage_network = 0
    if delete:
        wrapper.session.delete(wl)
    wrapper.session.commit()


def stop_services(device_uuid: str) -> None:
    m.contact_microservice("service", ["hardware", "stop"], {"device_uuid": device_uuid})


def delete_services(device_uuid: str) -> None:
    m.contact_microservice("service", ["hardware", "delete"], {"device_uuid": device_uuid})
