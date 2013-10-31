#!env python
# -*- coding:utf-8 -*-
# (C) 2011 Yojiro UO <yuo@nui.org> all right reserved.

'''
 * Copyright (c) 2011, 2013 Yojiro UO <yuo@nui.org>
 *
 * Permission to use, copy, modify, and distribute this software for any
 * purpose with or without fee is hereby granted, provided that the above
 * copyright notice and this permission notice appear in all copies.
 *
 * THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCAIMS ALL WARRANTIES
 * WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
 * MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
 * ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
 * WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
 * ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
 * OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.
'''

import json
import logging
import re
import socket
import struct
import sys
import unicodedata
from datetime import datetime,timedelta
from decimal import Decimal
from string import ascii_letters, digits, punctuation
from time import sleep

def dump_rawbuf(rawbuf):
    index = 0
    size = 16
    hexformat  = '{0:' + str(size*3) + '}'
    charformat = '{0:' + str(size) + '}'
    result = []
    if len(rawbuf) < size:
            size = len(rawbuf)
    while (index < len(rawbuf)):
        buf = []
        cbuf= []
        for i in range(size):    
            t = rawbuf[index + i]
            buf.append(t.encode('hex') + ' ')
            if (t in ascii_letters or t in digits or 
                t in punctuation or t == ' '):
                cbuf.append(t)
            else:
                cbuf.append('.')
        result.append(hexformat.format(''.join(buf)))
        result.append('|')
        result.append(charformat.format(''.join(cbuf)))
        result.append('|\n')
        index += size
        if len(rawbuf) - index < size:
            size = len(rawbuf) - index
    return ''.join(result)

class QAMessage(object):
    def __init__(self, header, body=None):
        self.QA_COOKIE_LEN = 30
        self.QA_LENGTH_LEN = 8
        self.header = header
        self.body = body
        m = re.match('(\d+)(\w+)', header)
        if m == None:
            print "unknown header?: %s" % header.encode('hex')
            raise ValueError
        if (m.end() != 10):
            raise ValueError
        if (m.group(1).isdigit()):
            self.bodylength = int(m.group(1))
        else:
            return None
        self.type = m.group(2)

    def body_length(self):
        return self.bodylength

    def add_body(self, body):
        if self.body is not None:
            logging.debug("this message already has body part")
            return None
        else:
            self.body = body

    def build_header(self, len, mesg_type=None):
        if mesg_type is None:
            mesg_type = self.type
        return str(len).zfill(self.QA_LENGTH_LEN) + mesg_type

    def is_ctrl_message(self):
        if re.match('EN|eN', self.type):
            return True
        else:
            return False

    def is_alert_message(self):
        if re.match('AN|aN', self.type):
            return True
        else:
            return False

    def is_healthcheck_request(self):
        if (self.body != None and self.body == 'chk'):
            return True
        else:
            return False

    def healthcheck_reply(self):
        body = "CHK"
        head = self.build_header(len(body))
        return head + body

    def is_require_checkpoint_reply(self):
        if re.match('aN|eN', self.type):
            return True
        else:
            return False

    def checkpoint_reply(self):
        if self.body is None:
            return None
        else:
            cp_body = 'ACK'
            cp_body += self.body[0:self.QA_COOKIE_LEN]
            head = self.build_header(len(cp_body))
            return head + cp_body

class QAlert(object):
    def __init__(self, body):
        self.QA_CODE_MAGIC   = '\xc5\xb3\xb7\xd4\xbd\xc43 \xb7\xbc\xd6\xb3'
        self.QA_DECODE_MAGIC = '\xc5\xb3\xb7\xd4\xbd\xc44 \xb7\xbc\xd6\xb3'
        self.QA_TEST_MAGIC   = '\xc5\xb3\xb7\xd4\xbd\xc4\xc3\xbd\xc41 \xb7\xbc\xd6\xb3'
        self.QA_TEST2_MAGIC  = '\xc5\xb3\xb7\xd4\xbd\xc4\xc3\xbd\xc491 \xb7\xbc\xd6\xb3'
        self.rawmessage = body
        b = body.splitlines()
        self.header = b[0]
        self.typestr = b[1]
        self.basic = b[3]
        self.message = b[4:]
        self.decode_basic_code()

    def decode_basic_code(self):
        b = self.basic.split()
        self.time_stamp = datetime.strptime(b[3], "%y%m%d%H%M%S")
        self.message_type = b[0]
        self.data_origin  = b[1]
        self.drill        = b[2]
        self.character    = b[4]

    def is_effective(self):
        if self.drill == '00':
            return True
        return False

    def is_alert(self):
        if re.match('35|36|37', self.message_type):
            return True
        return False

    def is_test(self):
        if self.message_type == '38':
            return True
        return False

    def is_canncel(self):
        if self.message_type == '39':
            return True
        return False

    def is_code_message(self):
        if self.typestr == self.QA_CODE_MAGIC:
            return True
        return False

    def is_decode_message(self):    
        if self.typestr == self.QA_DECODE_MAGIC:
            return True
        return False

    def is_test_message(self):
        if self.typestr == self.QA_TEST_MAGIC or \
           self.typestr == self.QA_TEST2_MAGIC:
            return True
        return False    

    def timestamp(self):
        return self.time_stamp

    def code_message(self):
        buf = []
        if self.is_code_message():
            for i in self.message[:-2]:
                buf.append(i + ' ')
        return ''.join(buf).rstrip()

    def decode_message(self):
        buf = []
        if self.is_decode_message() or self.is_test_message():
            for i in self.message[1:-2]:
                buf.append(unicode(i, 'shift-jis') + '\n')
        return unicodedata.normalize('NFKC', ''.join(buf))

    def printable_decode_message(self):
        return self.decode_message().replace(' ','').encode('utf-8')

    def dump_rawbuf(self):
        index = 0
        size = 16
        hexformat  = '{0:' + str(size*3) + '}'
        charformat = '{0:' + str(size) + '}'
        result = []
        if len(self.rawmessage) < size:
                size = len(self.rawmessage)
        while (index < len(self.rawmessage)):
            buf = []
            cbuf= []
            for i in range(size):    
                t = self.rawmessage[index + i]
                buf.append(t.encode('hex') + ' ')
                if (t in ascii_letters or t in digits or 
                    t in punctuation or t == ' '):
                    cbuf.append(t)
                else:
                    cbuf.append('.')
            result.append(hexformat.format(''.join(buf)))
            result.append('|')
            result.append(charformat.format(''.join(cbuf)))
            result.append('|\n')
            index += size
            if len(self.rawmessage) - index < size:
                size = len(self.rawmessage) - index
        return ''.join(result)


# location code translator: use this class if you dont'have DB file
class LocationDB(object):
    def __init__(self):
        self.__loaded = False

    def lookup(self, codestr, type='any'):
        if not re.match('\d{3}', codestr):
            logging.debug('location code error: %s', codestr)
            return None
        if type=='any':
            return codestr
        elif type=='ja' or type=='en' or type=='fr' or type=='kr':
            return codestr
        else:
            logging.debug('no such location type: %s', type)
            return None

# real location code translator: use this class if you have location DB.
class LocationDB_real(object):
    def __init__(self, json_file_name='quakealert/location_l10n.json'):
        self.dbfile = json_file_name
        self.__loaded = False

    def __loaddict(self):
        try:
            self.__db = json.load(open(self.dbfile))
        except IOError, (errno, strerror):
            logging.error('Location DB loading error: I/O error(%s): %s', 
                    errno, strerror)
        except ValueError, e:
            logging.error('Location DB error: %s', e)
        except:
            logging.error('Location DB loading error')
            raise
        else:
            self.__loaded = True

    def lookup(self, codestr, type='any'):
        if not self.__loaded:
            self.__loaddict()
        if not re.match('\d{3}', codestr):
            logging.debug('location code error: %s', codestr)
            return None
        try:
            entry = self.__db[codestr]
        except:
            logging.debug('location entry for %s is not found', codestr)
            return None
        if type=='any':
            return entry
        elif type=='ja' or type=='en' or type=='fr' or type=='kr':
            return entry[type]
        else:
            logging.debug('no such location type: %s', type)
            return None


class Parser(object):
    def __init__(self, message_type, codestr):
        self.codestr = codestr
        self.code = self.codestr.split(' ', 14)
        self.message_type = message_type
        self.rep = re.compile('([A-Z]+)([\d/]+)')
        self._ldb = LocationDB()

    def dump(self):
        d = {}
        d['message_type'] = self.message_type
        d['id'] = self.id()    
        d['timestamp'] = self.timestamp()
        d['is_last'] = self.is_last()
        d['is_first'] = self.is_first()
        d['alert_seq'] = self.alert_seq()
        d['location_code'] = self.location_code()
        d['location_str'] = self._ldb.lookup(self.location_code())
        d['geo'] = self.geo()
        d['depth'] = self.depth()
        d['magnitude'] = self.magnitude()
        d['max_seismic'] = self.max_seismic()
        d['area'] = self.area()
        d['rk'] = self.rk()
        d['rc'] = self.rc()
        d['ebi'] = self.ebi()
        return d

    def timestamp(self):
        return datetime.strptime(self.code[0], "%y%m%d%H%M%S")

    def is_first(self):
        if not self.is_last():
            if self.alert_seq() == 1:
                return True
        return False

    def is_last(self):
        if self.alert_condition() == '9':
            return True
        return False

    def id(self):
        rm = self.rep.match(self.code[1])
        if rm.group(1) == 'ND':
            if re.match('\d+', rm.group(2)):
                return rm.group(2)

    def alert_condition(self):
        rm = self.rep.match(self.code[2])
        if rm.group(1) == 'NCN':
            if re.match('\d+', rm.group(2)[0]):
                return rm.group(2)[0]

    def alert_seq(self):
        rm = self.rep.match(self.code[2])
        if rm.group(1) == 'NCN':
            if re.match('\d+', rm.group(2)[1:]):
                return int(rm.group(2)[1:])

    def location_code(self):
        if re.match('\d\d\d', self.code[5]):
            return self.code[5]

    def __latitude(self):
        if re.match('[NS]\d+', self.code[6]):
            return self.code[6]

    def __longitude(self):
            return self.code[7]

    def geo(self):
        g = []
        rp = re.compile('([NSEW])(\d+)')
        m_lat = rp.match(self.__latitude())
        m_long = rp.match(self.__longitude())
        if m_lat is None or m_long is None:
            return g
        latitude = Decimal(m_lat.group(2)) / Decimal(10)
        longitude = Decimal(m_long.group(2)) / Decimal(10)
        if m_lat.group(1) == 'S':
            latitude = latitude * -1
        if m_long.group(1) == 'W':
            longitude = longitude * -1
        g.append('%3.1f' % (latitude))
        g.append('%3.1f' % (longitude))
        return g

    def depth(self):
        if re.match('\d+', self.code[8]):
            return int(self.code[8])    

    def magnitude(self):
        if re.match('\d+', self.code[9]):
            return '%1.1f' % (Decimal(self.code[9]) / Decimal(10))

    def max_seismic(self):
        if self.message_type == '35':
            return None
        if self.code[10] == '//':
            return None
        if re.match('0[12347]', self.code[10]):
            return self.code[10][1:2]
        else:
            return self.code[10]

    def data_accuracy_code(self):
        rm = self.rep.match(self.code[11])
        if rm.group(1) == 'RK':
            return rm.group(2)

    def rk(self): # alias of data_accuracy_code()
        return self.data_accuracy_code()        

    def area(self):
        rm = self.rep.match(self.code[12])
        if rm.group(1) == 'RT':
            if rm.group(2)[0] == '0' or rm.group(2)[0] == '1':
                return int(rm.group(2)[0])

    def change_ratio_code(self):                
        rm = self.rep.match(self.code[13])
        if rm.group(1) == 'RC':
            return rm.group(2)

    def rc(self): # alias of change_ratio_code()
        return self.change_ratio_code()

    def __ebistr(self):
        if len(self.code) > 14:
            rm = re.match('(EBI)\s+(.+)', self.code[14])
            return rm.group(2)

    def ebi(self):
        if not self.__ebistr():
            return None
        ebi = ebi_parser(self.__ebistr()).ebi


class ebi_parser(object):
    def __init__(self, str):
        self.rawstr = str
        self.records = 0
        self.ebi = []
        s = self.rawstr.split()
        l = len(s)
        if l % 4 != 0:
            raise ValueError
        for i in range(int(l/4)): 
            e = s[i * 4 : (i+1) * 4]
            try:
                ebi = self.__build(e)
                self.ebi.append(ebi)
                self.records += 1
            except ValueError:
                continue

    def __build(self, list):
        if (len(list) != 4):
            raise ValueError
        ebi = {}
        if re.match('\d{3}', list[0]):
            ebi['location_code'] = list[0]
        m = re.match('S([\d+-/]{2})([\d+-/]{2})', list[1])
        seismic = []
        if m:
            for i in range(1,3):
                if re.match('0\d', m.group(i)):
                    seismic.append(m.group(i)[1:2])
                else:
                    if m.group(i) != '//':
                        seismic.append(m.group(i))
        ebi['seismic'] = seismic
        if re.match('\d{6}', list[2]):
            t = datetime.today()
            d = datetime.strptime('093032',"%H%M%S")
            ebi['timestamp'] = d.replace(t.year, t.month, t.day)
        else:
            ebi['timestamp'] = None
        if list[3] == '//':
            ebi['condition'] = None
        else:
            # XXX: mismatch real data and spec#216.
            # 0: not yet reached
            # 1: reached?
            # 10: not yet reached?
            # 11: reached?
            ebi['condition'] = int(list[3])
            if list[3][1:2] == '0':
                ebi['reached'] = False
            elif list[3][1:2] == '1':
                ebi['reached'] = True
        return ebi


class QAClient(object):
    def __init__(self, server, port, srcaddr=None):
        self.QA_HEADER_LEN = 10
        self.TIMEOUT = 120.0
        self.server = server
        self.port = port
        self.connected = False
        self.so = None
        self.connect_err_count = 0
        self.err_count = 0
        self.last_healthcheck_recved = None
        self.srcaddr = srcaddr
        self.verbose = None

    def __connect(self):
        if (self.connected):
            logging.debug("already connected")
            return True
        # exponencial backoff (up to 60 sec)
        if self.connect_err_count > 0:
            waittime = 2 ** self.connect_err_count
            if (waittime > 60):
                waittime = 60
            logging.error("connection error, wait %s sec", waittime)
            sleep (waittime)
        for res in socket.getaddrinfo(self.server, self.port, socket.AF_UNSPEC,
                socket.SOCK_STREAM):
            af, socktype, proto, canonname, sa = res
            try:
                self.so = socket.socket(af, socktype, proto)
            except socket.error, e:
                self.so = None
                logging.error("socket error:%s", e)
                continue
            try:
                self.so.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                self.so.settimeout(self.TIMEOUT)
                if self.srcaddr != None:
                    if af == socket.AF_INET:
                        ''' XXX, supporting ipv4 only, fix it '''
                        self.so.bind((self.srcaddr, 54322))
                self.so.connect(sa)
            except socket.error, e:
                self.so.close()
                logging.error("socket error:%s", e)
                self.so = None
                continue
            else:
                sa, sp = self.so.getsockname()
                pa, pp = self.so.getpeername()
                print "connected %s:%s -> %s:%s" % (sa, sp, pa, pp) 
            break
        if self.so is None:
            logging.error("could not open socket")
            self.connected = False
            return False
        else:
            logging.info("connected")
            self.err_count = 0
            self.connected = True
            return True

    def __close(self):
        if (self.connected):
            self.so.close()
            self.connected = False

    def __reconnect(self):
        self.__close()
        sleep (3)
        self.__connect()

    def __recv(self, len):
        buf = None
        if (self.connected):
            try:
                buf = self.so.recv(len)
            except socket.timeout, e:
                if self.last_healthcheck_recved is None:
                    logging.error("the process not yet recived health check \
                            request, any problem?")
                    return None
                delta = datetime.now() - self.last_healthcheck_recved 
                logging.info("%s sec passed from last healthckeck message \
                        recieved.", delta.seconds)
                if delta > timedelta(0, 5 * 60):
                    logging.error("too long absent of healtcheck reqest. \
                            try to reconect.")
                    self.__reconnect()
            except socket.error, e:
                print "%s" % (e)
            # as the socket is blocking socket, '' means the socket was 
            # disconected.
            if buf == '':
                logging.error("socket seems to be disconnected by remote peer,\
                        close local peer")
                self.connect_err_count += 1
                self.__close()
                return None
        else:
            logging.debug("socket not connected, connect first")
        return buf

    def __send(self, buffer):
        if (self.connected):
            try:
                self.so.sendall(buffer)
            except socket.error, e:
                logging.error("socket error:%s", e)
        else:
            logging.debug("socket not connected, connect first")

    def __reply_healthcheck(self, mesg):
        self.last_healthcheck_recved = datetime.now()
        buf = mesg.healthcheck_reply()
        if buf is not None:
            self.__send(buf)

    def __reply_checkpoint(self, mesg):
        buf = mesg.checkpoint_reply()
        if buf is not None:
            self.__send(buf)

    def stop(self):
        self.__close()

    def process(self):
        if self.connected is not True:
            status = self.__connect()
            if status is False:
                self.connect_err_count += 1
                return None
        header = self.__recv(self.QA_HEADER_LEN)
        if header is None:
            # socket err (incl. timeout)
            self.err_count += 1
            return None

        if self.verbose:
            try:
                print "=====debug====== (header part)"
                print dump_rawbuf(header)
            except:
                pass

        if len(header) != self.QA_HEADER_LEN:
            logging.info('bogus header: %s (len:%s)', header, len(header))
            # reconnect to server
            self.__close()
            return None    

        try:
            mesg = QAMessage(header)
        except:
            logging.info('QAMessage error')
            self.err_count += 1
            return None

        body = self.__recv(mesg.body_length())
        if body is None:
            self.err_count += 1
            return None
        if self.verbose:
            try:
                print "---(body part)---"
                print dump_rawbuf(body)
                sys.stdout.flush()
            except:
                pass

        mesg.add_body(body)
        # send back healthcheck reply
        if mesg.is_healthcheck_request():
            self.__reply_healthcheck(mesg)
            logging.info('Health Check request: acked')
        # send back checkpoint reply
        if mesg.is_require_checkpoint_reply():
            self.__reply_checkpoint(mesg)
            logging.info('CheckPoint request: acked')
        # process alert message 
        if mesg.is_alert_message():
            return mesg.body

