#!/usr/bin/env python3
"""Generate a full-coverage ACI imdata mock dataset for testing."""
import json
from pathlib import Path


def obj(cls, attrs):
    return {cls: {"attributes": attrs}}


def main():
    tenant = "tenantA"
    ap = "appA"
    bd = "bdA"
    vrf = "vrfA"
    epg1 = "web"
    epg2 = "db"
    phys_dom = "physDomA"
    vmm_dom = "vmmDomA"
    l3_dom = "l3DomA"
    vlan_pool = "vlanPoolA"

    leaf1 = "101"
    leaf2 = "102"
    spine1 = "201"
    fex_id = "301"

    imdata = []

    # Fabric nodes
    imdata.append(obj("fabricNode", {
        "dn": f"topology/pod-1/node-{leaf1}",
        "id": leaf1,
        "name": f"leaf-{leaf1}",
        "role": "leaf",
        "model": "N9K-C93180YC",
        "serial": "FDO1234567"
    }))
    imdata.append(obj("fabricNode", {
        "dn": f"topology/pod-1/node-{leaf2}",
        "id": leaf2,
        "name": f"leaf-{leaf2}",
        "role": "leaf",
        "model": "N9K-C93180YC",
        "serial": "FDO1234568"
    }))
    imdata.append(obj("fabricNode", {
        "dn": f"topology/pod-1/node-{spine1}",
        "id": spine1,
        "name": f"spine-{spine1}",
        "role": "spine",
        "model": "N9K-C9364C",
        "serial": "FDO9999999"
    }))

    # FEX
    imdata.append(obj("eqptFex", {
        "dn": f"topology/pod-1/node-{leaf1}/sys/extch-{fex_id}",
        "id": fex_id,
        "name": f"FEX-{fex_id}",
        "ser": "FOX1234567",
        "model": "N2K-C2248TP",
        "operSt": "up"
    }))

    # Tenant/VRF/BD/EPG
    imdata.append(obj("fvTenant", {
        "dn": f"uni/tn-{tenant}",
        "name": tenant
    }))
    imdata.append(obj("fvCtx", {
        "dn": f"uni/tn-{tenant}/ctx-{vrf}",
        "name": vrf
    }))
    imdata.append(obj("fvBD", {
        "dn": f"uni/tn-{tenant}/BD-{bd}",
        "name": bd,
        "arpFlood": "no",
        "unicastRoute": "yes"
    }))
    imdata.append(obj("fvRsCtx", {
        "dn": f"uni/tn-{tenant}/BD-{bd}/rsctx",
        "tDn": f"uni/tn-{tenant}/ctx-{vrf}",
        "tnFvCtxName": vrf
    }))

    imdata.append(obj("fvAEPg", {
        "dn": f"uni/tn-{tenant}/ap-{ap}/epg-{epg1}",
        "name": epg1
    }))
    imdata.append(obj("fvAEPg", {
        "dn": f"uni/tn-{tenant}/ap-{ap}/epg-{epg2}",
        "name": epg2
    }))

    imdata.append(obj("fvRsBd", {
        "dn": f"uni/tn-{tenant}/ap-{ap}/epg-{epg1}/rsbd",
        "tDn": f"uni/tn-{tenant}/BD-{bd}",
        "tnFvBDName": bd
    }))
    imdata.append(obj("fvRsBd", {
        "dn": f"uni/tn-{tenant}/ap-{ap}/epg-{epg2}/rsbd",
        "tDn": f"uni/tn-{tenant}/BD-{bd}",
        "tnFvBDName": bd
    }))

    # Subnet
    imdata.append(obj("fvSubnet", {
        "dn": f"uni/tn-{tenant}/BD-{bd}/subnet-[10.0.0.1/24]",
        "ip": "10.0.0.1/24",
        "scope": "private"
    }))

    # Path attachments (vPC protpaths)
    tdn_vpc = f"topology/pod-1/protpaths-{leaf1}-{leaf2}/pathep-[vpc-web]"
    imdata.append(obj("fvRsPathAtt", {
        "dn": f"uni/tn-{tenant}/ap-{ap}/epg-{epg1}/rspathAtt-[{tdn_vpc}]",
        "tDn": tdn_vpc,
        "encap": "vlan-10",
        "mode": "regular"
    }))
    tdn_leaf = f"topology/pod-1/paths-{leaf1}/pathep-[eth1/1]"
    imdata.append(obj("fvRsPathAtt", {
        "dn": f"uni/tn-{tenant}/ap-{ap}/epg-{epg2}/rspathAtt-[{tdn_leaf}]",
        "tDn": tdn_leaf,
        "encap": "vlan-20",
        "mode": "regular"
    }))

    # Physical interfaces
    imdata.append(obj("ethpmPhysIf", {
        "dn": f"topology/pod-1/node-{leaf1}/sys/phys-[eth1/1]",
        "operSt": "up",
        "operSpeed": "10G",
        "adminSt": "up",
        "usage": "regular"
    }))
    imdata.append(obj("ethpmPhysIf", {
        "dn": f"topology/pod-1/node-{leaf2}/sys/phys-[eth1/2]",
        "operSt": "down",
        "operSpeed": "10G",
        "adminSt": "down",
        "usage": "unused"
    }))

    # Domains and VLAN pools
    imdata.append(obj("physDomP", {
        "dn": f"uni/phys-{phys_dom}",
        "name": phys_dom
    }))
    imdata.append(obj("vmmDomP", {
        "dn": f"uni/vmmp-VMware/dom-{vmm_dom}",
        "name": vmm_dom
    }))
    imdata.append(obj("l3extDomP", {
        "dn": f"uni/l3dom-{l3_dom}",
        "name": l3_dom
    }))
    imdata.append(obj("fvnsVlanInstP", {
        "dn": f"uni/infra/vlanns-[{vlan_pool}]-static",
        "name": vlan_pool
    }))
    imdata.append(obj("fvnsEncapBlk", {
        "dn": f"uni/infra/vlanns-[{vlan_pool}]-static/from-[vlan-1]-to-[vlan-4094]",
        "from": "vlan-1",
        "to": "vlan-4094",
        "allocMode": "static"
    }))
    imdata.append(obj("infraRsVlanNs", {
        "dn": f"uni/phys-{phys_dom}/rsvlanNs",
        "tDn": f"uni/infra/vlanns-[{vlan_pool}]-static"
    }))
    imdata.append(obj("vmmRsVlanNs", {
        "dn": f"uni/vmmp-VMware/dom-{vmm_dom}/rsvlanNs",
        "tDn": f"uni/infra/vlanns-[{vlan_pool}]-static"
    }))
    imdata.append(obj("l3extRsVlanNs", {
        "dn": f"uni/l3dom-{l3_dom}/rsvlanNs",
        "tDn": f"uni/infra/vlanns-[{vlan_pool}]-static"
    }))

    # VPC/Port-channel/LACP
    imdata.append(obj("vpcDom", {
        "dn": f"topology/pod-1/node-{leaf1}/sys/vpc/inst/dom-1",
        "id": "1",
        "peerIp": "10.255.0.2",
        "virtualIp": "10.255.0.1",
        "operSt": "up",
        "role": "primary"
    }))
    imdata.append(obj("pcAggrIf", {
        "dn": f"topology/pod-1/node-{leaf1}/sys/aggr-[po10]",
        "id": "po10",
        "name": "po10"
    }))
    imdata.append(obj("lacpEntity", {
        "dn": f"topology/pod-1/node-{leaf1}/sys/lacp/inst",
        "mode": "active"
    }))
    imdata.append(obj("vpcIf", {
        "dn": f"topology/pod-1/node-{leaf1}/sys/vpc/inst/vpc-[vpc-web]",
        "name": "vpc-web",
        "id": "10"
    }))

    # Contracts and filters
    imdata.append(obj("vzBrCP", {
        "dn": f"uni/tn-{tenant}/brc-web",
        "name": "web",
        "scope": "context"
    }))
    imdata.append(obj("vzSubj", {
        "dn": f"uni/tn-{tenant}/brc-web/subj-http",
        "name": "http"
    }))
    imdata.append(obj("vzFilter", {
        "dn": f"uni/tn-{tenant}/flt-http",
        "name": "http"
    }))
    imdata.append(obj("vzEntry", {
        "dn": f"uni/tn-{tenant}/flt-http/entry-http",
        "name": "http",
        "prot": "tcp",
        "dFromPort": "80",
        "dToPort": "80",
        "sFromPort": "any",
        "sToPort": "any",
        "etherT": "ip"
    }))
    imdata.append(obj("vzRsSubjFiltAtt", {
        "dn": f"uni/tn-{tenant}/brc-web/subj-http/rssubjFiltAtt-[uni/tn-{tenant}/flt-http]",
        "tDn": f"uni/tn-{tenant}/flt-http"
    }))
    imdata.append(obj("fvRsCons", {
        "dn": f"uni/tn-{tenant}/ap-{ap}/epg-{epg1}/rscons-web",
        "tnVzBrCPName": "web"
    }))
    imdata.append(obj("fvRsProv", {
        "dn": f"uni/tn-{tenant}/ap-{ap}/epg-{epg2}/rsprov-web",
        "tnVzBrCPName": "web"
    }))

    # L3Out and routing
    imdata.append(obj("l3extOut", {
        "dn": f"uni/tn-{tenant}/out-inet",
        "name": "inet"
    }))
    imdata.append(obj("l3extInstP", {
        "dn": f"uni/tn-{tenant}/out-inet/instP-ext",
        "name": "ext"
    }))
    imdata.append(obj("l3extLNodeP", {
        "dn": f"uni/tn-{tenant}/out-inet/lnodep-nodeprof",
        "name": "nodeprof"
    }))
    imdata.append(obj("l3extLIfP", {
        "dn": f"uni/tn-{tenant}/out-inet/lnodep-nodeprof/lifp-1",
        "name": "lifp-1"
    }))
    imdata.append(obj("l3extRsNodeL3OutAtt", {
        "dn": f"uni/tn-{tenant}/out-inet/lnodep-nodeprof/rsnodeL3OutAtt-[topology/pod-1/node-{leaf1}]",
        "tDn": f"topology/pod-1/node-{leaf1}"
    }))
    imdata.append(obj("l3extSubnet", {
        "dn": f"uni/tn-{tenant}/out-inet/instP-ext/subnet-[0.0.0.0/0]",
        "ip": "0.0.0.0/0"
    }))
    imdata.append(obj("l3extRsEctx", {
        "dn": f"uni/tn-{tenant}/out-inet/rsectx",
        "tDn": f"uni/tn-{tenant}/ctx-{vrf}"
    }))
    imdata.append(obj("bgpPeerP", {
        "dn": f"uni/tn-{tenant}/out-inet/bgpeer-[1.1.1.1]",
        "addr": "1.1.1.1"
    }))
    imdata.append(obj("ospfIfP", {
        "dn": f"uni/tn-{tenant}/out-inet/ospfifp-1",
        "name": "ospfifp-1"
    }))
    imdata.append(obj("ipRouteP", {
        "dn": f"uni/tn-{tenant}/out-inet/iproutep-1",
        "name": "static-1"
    }))

    # Physical connectivity policy objects
    imdata.append(obj("infraAccPortGrp", {
        "dn": "uni/infra/funcprof/accportgrp-access",
        "name": "access"
    }))
    imdata.append(obj("infraAccBndlGrp", {
        "dn": "uni/infra/funcprof/accbundlegrp-vpc",
        "name": "vpc",
        "lagT": "node"
    }))
    imdata.append(obj("infraAccPortP", {
        "dn": "uni/infra/accportprof-1",
        "name": "portprof-1"
    }))
    imdata.append(obj("infraHPortS", {
        "dn": "uni/infra/accportprof-1/hports-1",
        "name": "hports-1",
        "type": "range"
    }))
    imdata.append(obj("infraAttEntityP", {
        "dn": "uni/infra/attentp-aep1",
        "name": "aep1"
    }))
    imdata.append(obj("infraRsDomP", {
        "dn": "uni/infra/attentp-aep1/rsdomP-[uni/phys-physDomA]",
        "tDn": f"uni/phys-{phys_dom}"
    }))
    imdata.append(obj("lldpAdjEp", {
        "dn": f"topology/pod-1/node-{leaf1}/sys/lldp/inst/if-[eth1/1]/adj-1",
        "sysName": "server1",
        "portIdV": "eth0"
    }))
    imdata.append(obj("cdpAdjEp", {
        "dn": f"topology/pod-1/node-{leaf2}/sys/cdp/inst/if-[eth1/2]/adj-1",
        "devId": "switch1",
        "portId": "Gi1/0/1",
        "platId": "N9K"
    }))

    out = {
        "imdata": imdata
    }

    output_path = Path("data/samples/sample_full_mock.json")
    output_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"Wrote {len(imdata)} objects to {output_path}")


if __name__ == "__main__":
    main()
