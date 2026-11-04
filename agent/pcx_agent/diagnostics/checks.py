"""As verificacoes do diagnostico: funcoes puras, que recebem os dados ja lidos do Windows.

Cada uma devolve uma lista (o antivirus pode ter um item por produto). Os textos dizem o que
esta acontecendo e o que fazer, em portugues simples.
"""

import ipaddress
import ntpath

from pcx_agent.diagnostics.model import (
    GROUP_AGENT,
    GROUP_ANTIVIRUS,
    GROUP_NETWORK,
    GROUP_SENSORS,
    AgentProbe,
    CheckResult,
    FirewallRule,
    SecurityProduct,
)
from pcx_agent.network import NetInterface, is_virtual
from pcx_agent.sensors.base import GpuReading, Snapshot

RULE_NAME = "PcX Control - agente"
# So VPNs de verdade (as placas virtuais de Hyper-V, WSL e afins nao atrapalham o celular).
VPN_NAMES = ("radmin", "hamachi", "zerotier", "tailscale", "wireguard", "openvpn", "tap-windows", "vpn")
VPN_NETWORKS = tuple(ipaddress.ip_network(n) for n in ("26.0.0.0/8", "25.0.0.0/8", "100.64.0.0/10"))
_APIPA = ipaddress.ip_network("169.254.0.0/16")
VENDOR_LABELS = {"nvidia": "NVIDIA", "amd": "AMD", "intel": "Intel"}


def _result(id_: str, group: str, title: str, status, detail: str, fix=None) -> list[CheckResult]:
    return [CheckResult(id_, group, title, status, detail, fix)]


def check_ip(interfaces: list[NetInterface], chosen: NetInterface | None) -> list[CheckResult]:
    title = "IP da rede local"
    if chosen is not None:
        return _result("rede.ip", GROUP_NETWORK, title, "ok", f"{chosen.ipv4} na placa {chosen.name}.")
    up = [i for i in interfaces if i.up]
    if any(ipaddress.ip_address(i.ipv4) in _APIPA for i in up):
        return _result(
            "rede.ip", GROUP_NETWORK, title, "problema",
            "O roteador não entregou um IP para este PC (endereço 169.254.x.x). "
            "Reinicie o roteador ou desconecte e conecte o cabo ou o Wi-Fi.",
        )
    if any(is_virtual(i.name, i.ipv4) for i in up):
        return _result(
            "rede.ip", GROUP_NETWORK, title, "problema",
            "Só há VPN ou placa virtual ligada. Conecte o PC ao mesmo roteador do celular "
            "(cabo ou Wi-Fi).",
        )
    return _result(
        "rede.ip", GROUP_NETWORK, title, "problema",
        "O PC está sem rede. Conecte ao mesmo roteador do celular.",
    )


def check_network_type(chosen: NetInterface | None, profiles: dict[str, str] | None) -> list[CheckResult]:
    title = "Tipo de rede no Windows"
    category = (profiles or {}).get(chosen.name) if chosen is not None else None
    if category is None:
        return _result(
            "rede.tipo", GROUP_NETWORK, title, "info",
            "Não deu para ler o tipo de rede do Windows. Confira em Configurações > Rede se ela "
            "está como Privada.",
        )
    if category == "public":
        return _result(
            "rede.tipo", GROUP_NETWORK, title, "problema",
            f"A rede da placa {chosen.name} está como Pública: o Windows bloqueia o celular. "
            "Mude para Privada.",
            "abrir_rede",
        )
    if category == "domain":
        return _result(
            "rede.tipo", GROUP_NETWORK, title, "atencao",
            "Rede de domínio (empresa): a regra do firewall do PcX Control vale só para rede "
            "Privada. Fale com quem administra a rede.",
        )
    return _result("rede.tipo", GROUP_NETWORK, title, "ok", f"A rede da placa {chosen.name} está como Privada.")


def _same_program(a: str | None, b: str) -> bool:
    if not a:
        return False
    # Caminhos do Windows: sem diferenca de maiusculas, com / ou \\, em qualquer sistema.
    return ntpath.normcase(ntpath.normpath(a)) == ntpath.normcase(ntpath.normpath(b))


def check_firewall(rules: list[FirewallRule] | None, exe_path: str | None) -> list[CheckResult]:
    title = "Regra do firewall"
    if exe_path is None:
        return _result(
            "rede.firewall", GROUP_NETWORK, title, "info",
            "Rodando pelo código, sem o instalador: a regra do firewall é criada pelo instalador.",
        )
    if rules is None:
        return _result(
            "rede.firewall", GROUP_NETWORK, title, "info",
            "Não deu para ler as regras do firewall do Windows.",
        )
    ours = [r for r in rules if r.name == RULE_NAME]
    if not ours:
        detail = f'A regra "{RULE_NAME}" não existe: o Windows bloqueia o celular.'
    else:
        good = [
            r for r in ours
            if r.enabled and r.direction == "in" and r.action == "allow"
            and r.profiles & {"private", "any"} and _same_program(r.program, exe_path)
        ]
        if good:
            return _result("rede.firewall", GROUP_NETWORK, title, "ok", "A regra do PcX Control está ativa na rede Privada.")
        rule = ours[0]
        if not rule.enabled:
            detail = "A regra do PcX Control existe, mas está desativada."
        elif rule.direction != "in" or rule.action != "allow":
            detail = "A regra do PcX Control não está liberando conexões de entrada."
        elif not rule.profiles & {"private", "any"}:
            detail = "A regra do PcX Control não vale para a rede Privada."
        else:
            detail = "A regra do PcX Control aponta para outro programa (talvez de uma instalação antiga)."
    return _result("rede.firewall", GROUP_NETWORK, title, "problema", detail + " Crie a regra de novo.", "criar_firewall")


def _is_vpn(interface: NetInterface) -> bool:
    name = interface.name.lower()
    if any(word in name for word in VPN_NAMES):
        return True
    try:
        return any(ipaddress.ip_address(interface.ipv4) in n for n in VPN_NETWORKS)
    except ValueError:
        return False


def check_vpn(interfaces: list[NetInterface]) -> list[CheckResult]:
    title = "VPN"
    names = sorted({i.name for i in interfaces if i.up and _is_vpn(i)})
    if not names:
        return _result("rede.vpn", GROUP_NETWORK, title, "ok", "Nenhuma VPN ligada.")
    return _result(
        "rede.vpn", GROUP_NETWORK, title, "atencao",
        f"VPN ligada: {', '.join(names)}. O PcX Control usa a rede local, mas algumas VPNs "
        "bloqueiam o acesso a ela. Se o celular não conectar, desligue a VPN e teste de novo.",
    )


def check_agent(
    probe: AgentProbe, address: str, server_error: str | None = None, server_running: bool = True
) -> list[CheckResult]:
    title = "Agente respondendo na rede"
    if server_error == "port_in_use":
        return _result(
            "agente.local", GROUP_AGENT, title, "problema",
            "A porta do PcX Control já está em uso por outro programa, então o agente não está "
            "no ar. Troque a porta.",
            "trocar_porta",
        )
    if not server_running:
        return _result(
            "agente.local", GROUP_AGENT, title, "problema",
            "O servidor do agente está parado. Reinicie o servidor.",
            "reiniciar_servidor",
        )
    note = " (teste feito de dentro do PC: não prova o caminho até o celular)"
    if probe.reachable and probe.same_agent:
        return _result("agente.local", GROUP_AGENT, title, "ok", f"O agente responde em {address}{note}.")
    if probe.reachable:
        detail = f"Outro programa respondeu em {address}. Feche-o ou troque a porta do PcX Control."
        return _result("agente.local", GROUP_AGENT, title, "problema", detail, "trocar_porta")
    else:
        detail = f"O agente não respondeu em {address}: {probe.error or 'sem resposta'}."
    return _result("agente.local", GROUP_AGENT, title, "problema", detail)


def check_antivirus(products: list[SecurityProduct] | None) -> list[CheckResult]:
    title = "Antivírus e firewall de terceiros"
    if products is None:
        return _result(
            "antivirus.terceiros", GROUP_ANTIVIRUS, title, "info",
            "Não deu para ler os antivírus instalados (Central de Segurança do Windows).",
        )
    others = sorted(
        {(p.name, p.kind) for p in products if p.enabled and not p.from_windows}, key=lambda x: x[0].lower()
    )
    if not others:
        return _result(
            "antivirus.terceiros", GROUP_ANTIVIRUS, title, "ok",
            "Só a proteção do Windows está ativa.",
        )
    return [
        CheckResult(
            "antivirus.terceiros", GROUP_ANTIVIRUS, name, "atencao",
            f"{'Firewall' if kind == 'firewall' else 'Antivírus'} de terceiros ativo. "
            f"Libere este programa no {name}.",
            "copiar_caminho",
        )
        for name, kind in others
    ]


def check_gpus(gpus: list[GpuReading]) -> list[CheckResult]:
    if not gpus:
        return _result(
            "sensores.gpu", GROUP_SENSORS, "Placa de vídeo", "atencao",
            "Nenhuma placa de vídeo encontrada: o app não vai mostrar a GPU.",
        )
    results = []
    for index, gpu in enumerate(gpus):
        parts = [f"Fabricante: {VENDOR_LABELS.get(gpu.vendor or '', 'outro')}"]
        if gpu.vram_total_bytes:
            parts.append(f"VRAM {gpu.vram_total_bytes / 1024**3:.1f} GiB")
        parts.append("temperatura disponível" if gpu.temp_c is not None else "sem temperatura")
        if index == 0:
            parts.append("é a mostrada no app")
        results.append(CheckResult("sensores.gpu", GROUP_SENSORS, gpu.name, "info", "; ".join(parts) + "."))
    return results


def check_reading(
    snapshot: Snapshot | None, error: str | None, age_s: float | None = None, stale_after_s: float = 30.0
) -> list[CheckResult]:
    title = "Leitura dos sensores"
    if snapshot is None:
        return _result(
            "sensores.leitura", GROUP_SENSORS, title, "problema",
            f"A leitura falhou: {error or 'sem dados'}.", "reiniciar_sensores",
        )
    if age_s is not None and age_s > stale_after_s:
        return _result(
            "sensores.leitura", GROUP_SENSORS, title, "problema",
            f"Os sensores pararam de responder há {age_s:.0f} s.", "reiniciar_sensores",
        )
    return _result(
        "sensores.leitura", GROUP_SENSORS, title, "ok",
        f"CPU, memória, {len(snapshot.disks)} disco(s) e rede lidos.",
    )
