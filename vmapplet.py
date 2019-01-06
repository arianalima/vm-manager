#!/usr/bin/env python
import libvirt

conn = libvirt.open("qemu:///system")

for id in conn.listDomainsID():
    dom = conn.lookupByID(id)
    infos = dom.info()
    print ('ID = %d' %id)
    print ('Name = %s' %dom.name())
    print ('State = %d' %infos[0]) # 1 ativo    3 pausado
    print ('Max Memory = %d' %infos[1])
    print ('Number of virt CPUs = %d' %infos[3])
    print ('CPU time (in ns) = %d' %infos[2])
    print (' ')

domains = conn.listAllDomains()
data = domains[0].XMLDesc()

f = open("vm-template.xml",'w')
f.write(data)
f.close()
