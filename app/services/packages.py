from dataclasses import dataclass


@dataclass(frozen=True)
class Package:
    code: str
    name: str
    amount: int
    duration: str
    mikrotik_profile: str
    limit_uptime: int


PACKAGES: dict[str, Package] = {
 "1H": Package(
    code="1H",
    name="Saa 1",
    amount=436,
    duration="1h",
    mikrotik_profile="VOUCHER-1HOUR",
    limit_uptime=3600,
),
    "24H": Package(
        code="24H",
        name="Masaa 24",
        amount=936,
        duration="24h",
        mikrotik_profile="VOUCHER-24HOUR",
        limit_uptime=86400,
    ),
    "3D": Package(
        code="3D",
        name="Siku 3",
        amount=2736,
        duration="3d",
        mikrotik_profile="VOUCHER-3DAY",
        limit_uptime=259200,
    ),
    "7D": Package(
        code="7D",
        name="Wiki 1",
        amount=12000,
        duration="7d",
        mikrotik_profile="7D",
        limit_uptime=604800,
    ),
    "30D": Package(
        code="30D",
        name="Mwezi 1",
        amount=30000,
        duration="30d",
        mikrotik_profile="30D",
        limit_uptime=2592000,
    ),
}


def get_package(package_code: str) -> Package:
    package = PACKAGES.get(package_code.upper())

    if package is None:
        raise ValueError(f"Unknown package: {package_code}")

    return package


def get_all_packages() -> list[Package]:
    return list(PACKAGES.values())