from typing import List, Optional
from scheme import *
from app import m, wrapper
from models.device import Device


@m.user_endpoint(path=["device", "info"])
def info(data: dict, user: str) -> dict:
    """
    Get public information about a device.
    :param data: The given data.
    :param user: The user uuid.
    :return: The response
    """
    device: Optional[Device] = wrapper.session.query(Device).filter_by(uuid=data["device_uuid"]).first()

    if device is None:
        return invalid_device

    return device.serialize


@m.user_endpoint(path=["device", "ping"])
def ping(data: dict, user: str) -> dict:
    """
    Ping a device.
    :param data: The given data.
    :param user: The user uuid.
    :return: The response
    """
    device: Optional[Device] = wrapper.session.query(Device).filter_by(uuid=data["device_uuid"]).first()

    if device is None:
        return invalid_device

    return {
        "online": device.powered_on
    }


@m.user_endpoint(path=["device", "all"])
def get_all(data: dict, user: str) -> dict:
    """
    Get all devices
    :param data: The given data.
    :param user: The user uuid.
    :return: The response
    """
    devices: List[Device] = wrapper.session.query(Device).filter_by(owner=user).all()

    return {
        "devices": [d.serialize for d in devices]
    }


@m.user_endpoint(path=["device", "create"])
def create(data: dict, user: str) -> dict:
    """
    Create a device.
    :param data: The given data.
    :param user: The user uuid.
    :return: The response
    """
    device_count = wrapper.session.query(Device).filter_by(owner=user).first()

    if device_count:
        return already_have_device

    device: Device = Device.create(user, 1, True)

    return device.serialize


@m.user_endpoint(path=["device", "power"])
def power(data: dict, user: str) -> dict:
    """
    Turn a device on/off.
    :param data: The given data.
    :param user: The user uuid.
    :return: The response
    """
    device: Device = wrapper.session.query(Device).filter_by(uuid=data['device_uuid']).first()

    if device is None:
        return invalid_device

    if not device.check_access(user):
        return permission_denied

    device.powered_on: bool = not device.powered_on
    wrapper.session.commit()

    return device.serialize


@m.user_endpoint(path=["device", "change_name"])
def change_name(data: dict, user: str) -> dict:
    """
    Change the name of the device.
    :param data: The given data.
    :param user: The user uuid.
    :return: The response
    """
    device: Optional[Device] = wrapper.session.query(Device).filter_by(uuid=data['device_uuid']).first()

    if device is None:
        return invalid_device

    if not device.check_access(user):
        return permission_denied
    try:
        name: str = str(data['name'])
    except KeyError:
        return no_name

    if len(name) > 15:
        return name_too_long

    device.name: str = name

    wrapper.session.commit()

    return device.serialize


@m.user_endpoint(path=["device", "delete"])
def delete(data: dict, user: str) -> dict:
    """
    Delete a device.
    :param data: The given data.
    :param user: The user uuid.
    :return: Success or not
    """
    device: Device = wrapper.session.query(Device).filter_by(uuid=data['device_uuid']).first()

    if device is None:
        return invalid_device

    if not device.check_access(user):
        return permission_denied

    wrapper.session.delete(device)
    wrapper.session.commit()

    return success


@m.user_endpoint(path=["device", "spot"])
def spot(data: dict, user: str) -> dict:
    device: Device = Device.random(user)

    return device.serialize


@m.microservice_endpoint(path=["exist"])
def exist(data: dict, microservice: str) -> dict:
    """
    Does a device exist?
    :param data: The given data.
    :param microservice: The microservice..
    :return: True or False
    """
    device: Optional[Device] = wrapper.session.query(Device).filter_by(uuid=data["device_uuid"]).first()

    return {
        'exist': device is not None
    }


@m.microservice_endpoint(path=["owner"])
def owner(data: dict, microservice: str) -> dict:
    device: Optional[Device] = wrapper.session.query(Device).filter_by(uuid=data["device_uuid"]).first()

    if device is None:
        return this_device_does_not_exists
    else:
        return {"owner": device.owner}
