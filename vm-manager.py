import libvirt
import random
import uuid

from xml.dom import minidom
from shutil import copy2

from flask import Flask, render_template, redirect, jsonify
from flask_wtf import FlaskForm
from flask_bootstrap import Bootstrap
from wtforms import StringField, IntegerField, SelectField
from wtforms.validators import InputRequired, IPAddress


app = Flask(__name__, template_folder='templates')
Bootstrap(app)
app.config.update(dict(
    SECRET_KEY="SECRET",
    WTF_CSRF_SECRET_KEY="SECRET"
))

conn = libvirt.open('qemu:///system')
domains = conn.listAllDomains()
uuidx = '03a1126a-7a77-469f-9d2a-94f072da3b3e'

base = 1024
memory = {
    'KiB': lambda number: number,
    'MiB': lambda number: number * base,
    'GiB': lambda number: memory['MiB'](number) * base
}

def is_number(number):
    if number != None and type(number) == int:
        return True
    return False

def is_word(word):
    if word != None and type(word) == str:
        return True
    return False

def set_correct_size(number, unity):
    if is_number(number):
        size = memory[unity](number)
        return size
    return 0

def set_memory_to(doc, number, unity):
    size = set_correct_size(number, unity)
    if size:
        replace_text(doc, 'memory', size)
        replace_text(doc, 'currentMemory', size)
        return size
    return size

def set_cpu_to(doc, number):
    if is_number(number):
        replace_text(doc, "vcpu", number)
        return number
    return 0

def set_mac_to(doc, mac):
    if is_word(mac):
        replace_text(doc, "mac", mac, "address")
        return mac
    return ''

def set_new_hostname(doc, hostname):
    if is_word(hostname):
        replace_text(doc, "name", hostname)
        return hostname
    return ''

def genarate_new_uuid(doc):
    uuidx = str(uuid.uuid1())
    replace_text(doc, "uuid", uuidx)
    return uuidx

def get_xml_from_domain(domain):
    data = domain.XMLDesc()
    xml = minidom.parseString(data)
    return xml

def get_mac_from_domain(domain):
    xml = get_xml_from_domain(domain)
    node = xml.getElementsByTagName('mac')
    mac = node[0].attributes['address'].value
    return mac

def replace_text(doc, name, value, attribute=None):
    node = doc.getElementsByTagName(name)[0]
    if attribute:
        node.attributes[attribute].value = value
        return
    node.firstChild.nodeValue = value


def random_mac():
    mac = [0x00, 0x16, 0x3e,
           random.randint(0x00, 0x7f),
           random.randint(0x00, 0xff),
           random.randint(0x00, 0xff)]
    return ':'.join(map(lambda x: "%02x" % x, mac))


def generate_unique_mac():
    mac = random_mac()
    macs = map(get_mac_from_domain, domains)
    while mac in macs:
        mac = random_mac()
    return mac


def update_network_settings(mac, ip):
    template_ip = f'<host mac="{mac}" ip="{ip}"/>'
    network = conn.networkLookupByName("default")
    result = network.update(libvirt.VIR_NETWORK_UPDATE_COMMAND_ADD_FIRST, libvirt.VIR_NETWORK_SECTION_IP_DHCP_HOST, -1,
                            template_ip)
    return result

def configure_network(doc, ip):
    result = ''
    if is_word(ip):
        mac = generate_unique_mac()
        result = set_mac_to(doc, mac)
        if result:
            result = update_network_settings(mac, ip)
    return result

def clone_harddisk(doc, hostname):
    disk = doc.getElementsByTagName("disk")[0]
    source = disk.getElementsByTagName("source")[0]
    folder = source.attributes['file'].value

    filename = folder.split('/').pop()
    extension = filename.split('.').pop()
    filename = f'{hostname}.{extension}'
    path = f"/home/ariana/Documentos/{filename}"
    copy2(folder, path)
    source.attributes['file'].value = path

class VirtForm(FlaskForm):
    hostname = StringField('Hostname:', validators=[InputRequired()])
    memory = IntegerField('Memory:', validators=[InputRequired()])
    ipv4 = StringField('IPv4:', validators=[InputRequired(), IPAddress(ipv4=True, ipv6=False)])
    cpu = IntegerField("CPU:", validators=[InputRequired()])
    unity = SelectField("Unity:", choices=[('KiB', 'KiB'), ('MiB', 'MiB'), ('GiB', 'GiB')],
                        validators=[InputRequired()])

@app.route('/')
def index():
    return redirect("/form", code=302)

@app.route('/form', methods=['GET', 'POST'])
def form():
    form = VirtForm()
    if form.validate_on_submit():
        print("clone init!")
        domain = conn.lookupByUUIDString(uuidx)
        state, reason = domain.state()

        if state == libvirt.VIR_DOMAIN_RUNNING:
            domain.suspend()
            while domain.state()[0] == libvirt.VIR_DOMAIN_RUNNING:
                pass

        document = domain.XMLDesc()
        clone_xml = minidom.parseString(document)
        print("clone disk...")
        clone_harddisk(clone_xml, form.hostname.data)
        print("set new uuid...")
        genarate_new_uuid(clone_xml)
        print("set new vm-alias...")
        set_new_hostname(clone_xml, form.hostname.data)
        print("set memory size...")
        set_memory_to(clone_xml, form.memory.data, form.unity.data)
        print("set cpu...")
        set_cpu_to(clone_xml, form.cpu.data)
        configure_network(clone_xml, form.ipv4.data)

        print("init vms!")
        result = clone_xml.toxml()
        clone = conn.defineXML(result)
        clone.create()
        domain.resume()

        result = {}
        result['hostname'] = form.hostname.data
        result['ipv4'] = form.ipv4.data
        result["memory"] = {"size": form.memory.data, "unity": form.unity.data}
        result["cpu"] = form.cpu.data
        return jsonify(result)
    return render_template('form.html', form=form)

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0')
