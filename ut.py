#!/usr/bin/python
'''
Created on Jan 9, 2015

@author: William.George
'''

import unittest
import sshutil
from optparse import OptionParser


class sshutilFINtc(unittest.TestCase):

    def setUp(self):

        self.FIN_suffixes = ['1', '1/0/1', '0/1']
        self.FIN_values = []
        self.FIN_values.append(
            ['GigabitEthernet', 'Gi', 'gigab', 'GIgaBIT', 'gi'])
        self.FIN_values.append(['FastEthernet', 'Fa', 'faste', 'fAsTeT', 'fa'])
        self.FIN_values.append(['Serial', 'Se', 'seria', 'sErIAl', 'se'])
        self.FIN_values.append(['Port-Channel', 'Po', 'port-cha', 'PoRT-Cha',
                                'po'])
        self.FIN_values.append(['Ethernet', 'E', 'ethern', 'ETherNE', 'e'])
        self.FIN_values.append(['Vlan', 'Vl', 'vlan', 'vLaN', 'vl'])
        self.FIN_values.append(['TenGigabitEthernet', 'Te', 'tengigab',
                                'TenGIG', 'te'])

    def test_FIN_to_Short(self):
        for valueset in self.FIN_values:
            LongPrefix = valueset[0]
            ShortPrefix = valueset[1]
            DirtyInputs = [LongPrefix] + valueset[2:]
            for dirtyPrefix in DirtyInputs:
                for suffix in self.FIN_suffixes:
                    dirtyInput = dirtyPrefix + suffix
                    rslt = sshutil.FormatInterfaceName(dirtyInput, short=True)
                    # print dirtyInput, rslt
                    self.assertEqual(rslt, ShortPrefix + suffix, 'failed: {0}'
                                     ' didn\'t return {1}'
                                     ''.format(rslt, ShortPrefix + suffix))
            for dirty in ['', None]:
                rslt = sshutil.FormatInterfaceName(dirty, short=True)
                self.assertEqual(rslt, dirty, 'failed: {0} didn\'t return '
                                 '{1}'.format(rslt, dirty))

    def test_FIN_to_Long(self):
        for valueset in self.FIN_values:
            LongPrefix = valueset[0]
            ShortPrefix = valueset[1]
            DirtyInputs = [ShortPrefix] + valueset[2:]
            for dirtyPrefix in DirtyInputs:
                for suffix in self.FIN_suffixes:
                    # print dirtyPrefix, dirtyPrefix[:2], suffix
                    dirtyInput = dirtyPrefix + suffix
                    rslt = sshutil.FormatInterfaceName(dirtyInput, short=False)
                    self.assertEqual(rslt, LongPrefix + suffix, 'failed: {0}'
                                     ' didn\'t return {1}'
                                     ''.format(rslt, LongPrefix + suffix))
            for dirty in ['', None]:
                rslt = sshutil.FormatInterfaceName(dirty, short=False)
                self.assertEqual(rslt, dirty, 'failed: {0} didn\'t return '
                                 '{1}'.format(rslt, dirty))


class sshutilSwitchTC(unittest.TestCase):

    def setUp(self):

        self.sampleData = {}
        self.sampleData['CDPNeighborDetail'] = ['sample/ShowCDPNeiDet', '']
        self.sampleData['Interface'] = ['sample/ShowInt', '']
        self.sampleData['InterfaceDescription'] = \
            ['sample/ShowIntDes', '']
        self.sampleData['InterfaceSwitchport'] = \
            ['sample/ShowIntSwitchport', '']
        self.sampleData['MacAddressTable'] = ['sample/ShowMacAddressTable', '']

        for i in self.sampleData:
            with open(self.sampleData[i][0], 'r') as fSampleData:
                self.sampleData[i][1] = fSampleData.read()

        self.sampleData['IP'] = ['10.217.225.140']

    def test_SwitchGetInterfaces(self):
        sw = sshutil.clSwitch(ip=self.sampleData['IP'][0], creds=None)
        self.assertEqual(sw.state, 'UNK', 'switch.state doesn\'t'
                         'default to "UNK"')
        sw.GetInterfaces(data=self.sampleData['Interface'][1])
        self.assertEqual(sw.state, 'UP', 'switch.state doesn\'t set to "UP"')
        self.assertEqual(len(sw.ports), 55, 'len(switch.ports) == {0}'
                         ''.format(len(sw.ports)))
        self.assertEqual(sw.ports[1].name, 'Vlan2', 'misnamed/numbered Vlan2')
        self.assertEqual(sw.ports[21].name, 'FastEthernet1/0/19',
                         'misnamed/numbered Fa1/0/19')
        self.assertEqual(sw.ports[21].description,
                         '%End Device: NONE; Date: 06-01-2015',
                         'Bad description on {0} : {1}'
                         ''.format(sw.ports[21], sw.ports[21].description))
        self.assertEqual(sw.ports[22].description,
                         '%End Device: mac:0026.b9f0.095e '
                         'host:blcl28265; Date: 06-01-2015'
                         ''.format(sw.ports[22], sw.ports[22].description))
        self.assertEqual(sw.ports[51].description, '%Connection To: '
                         'CORE4507-2 IP:10.217.224.2 Date: '
                         '06-01-2015', 'Bad Description on {0} : {1}'
                         ''.format(sw.ports[51], sw.ports[51].description))

    def test_SwitchClassifyPorts(self):
        sw = sshutil.clSwitch(ip=self.sampleData['IP'][0], creds=None)
        sw.GetInterfaces(data=self.sampleData['Interface'][1])
        sw.ClassifyPorts(self.sampleData['InterfaceSwitchport'][1])
        print sw
        pass


class sshutilSwitchPortTC(unittest.TestCase):
    def setUp(self):
        self.sampleData = {}
        self.sampleData['get_edge'] = [
            [
                # [[(CDPNeigh)],
                [('sampledata', 'sampledata', ['sample', 'data', 'switch'])],
                # switchportMode,
                'access',
                # expected_result]
                False
            ],
            [
                [('sampledata', 'sampledata', ['sample', 'data', 'phone'])],
                'access',
                True
            ],
            [
                [('sampledata', 'sampledata', ['sample', 'bridge', 'phone'])],
                'access',
                True
            ],
            [
                [('sampledata', 'sampledata', ['sample', 'data', 'rouTEr'])],
                'access',
                False
            ],
            [
                [('sampledata', 'sampledata', ['phone']),
                 ('sampledata', 'sampledata', ['switch'])],
                'access',
                False
            ],
            [
                [('sampledata', 'sampledata', [])],
                'aCCess',
                True
            ],
            [
                [],
                'Trunk',
                False
            ]
        ]

    def test_init(self):
        try:
            sp = sshutil.clSwitchPort()
        except Exception as E:
            self.fail('clswitchport._init_() threw an exception!')
            raise E

    def test_get_edge(self):
        sp = sshutil.clSwitchPort()
        for sample in self.sampleData['get_edge']:
            eRslt = sample[2]  # expected Result
            aRslt = sp._get_edge(sample[0], sample[1])
            msg = ('clswitchport._get_edge() returned an incorrect result!\n'
                   'SampleData:\n    CDPNeigh:{0}\n    switchportMode:{1}'
                   '\n    Expected:{2}\n    Returned:{3}\n'
                   ''.format(sample[0], sample[1], eRslt, aRslt))
            self.assertEqual(eRslt, aRslt, msg)

    def test_switchportMode(self):
        sp = sshutil.clSwitchPort()
        self.assertEqual(sp.switchportMode, 'access', 'clswitchportMode'
                         'default\n    Expected: {0}\n    Returned: {1}\n'
                         ''.format('access', sp.switchportMode))
        sp.switchportMode = 'somethingUndefined'
        self.assertEqual(sp.switchportMode, 'unknown', 'clswitchporMode'
                         'improper handling of undefined case:\n'
                         '    Expected: {0}\n    Returned: {1}\n'
                         ''.format('unknown', sp.switchportMode))
        sp.switchportMode = 'TRUNK'
        self.assertEqual(sp.switchportMode, 'trunk', 'clswitchportMode'
                         'improper handling of \'TRUNK\':\n'
                         '    Expected: {0}\n    Returned: {1}\n'
                         ''.format('trunk', sp.switchportMode))


def ts_FIN():
    FIN_tests = ['test_FIN_to_Short', 'test_FIN_to_Long']
    suite_FormatInterfaceName = unittest.TestSuite(
        map(sshutilFINtc, FIN_tests))
    return suite_FormatInterfaceName


def ts_SwitchGetInterfaces():
    SW_tests = ['test_SwitchGetInterfaces']
    suite_clSwitch = unittest.TestSuite(
        map(sshutilSwitchTC, SW_tests))
    return suite_clSwitch


def ts_SwitchClassifyPorts():
    SW_tests = ['test_SwitchClassifyPorts']
    suite_clSwitch = unittest.TestSuite(
        map(sshutilSwitchTC, SW_tests))
    return suite_clSwitch


def ts_Switchport():
    SP_tests = ['test_init', 'test_get_edge', 'test_switchportMode']
    suite_clSwitchPort = unittest.TestSuite(
        map(sshutilSwitchPortTC, SP_tests))
    return suite_clSwitchPort


def createParser():
    usage = 'usage: %prog [options] arg'
    testSuiteHelp = ('What test suite to run.                             '
                     'Default:                                        all '
                     'fin:                    sshutil.formatinterfacename '
                     'switchgi:                  clSwitch.GetInterfaces() '
                     'switchcp:                  clSwitch.ClassifyPorts() '
                     'switchport:          clSwitchPort, multiple methods '
                     'all:                               self explanatory ')
    parser = OptionParser(usage)
    parser.add_option('-v', '--verbose', action='store_true', dest='verbose')
    parser.add_option('-t', '--testsuite', action='store', dest='suite',
                      help=testSuiteHelp)
    parser.set_default('suite', 'all')
    return parser


def main():
    parser = createParser()
    (options, args) = parser.parse_args()
    print options
    suite = options.suite.lower()

    if suite == 'fin':
        ts_Suite = ts_FIN()
    elif suite == 'switchgi':
        ts_Suite = ts_SwitchGetInterfaces()
    elif suite == 'switchport':
        ts_Suite = ts_Switchport()
    elif suite == 'switchcp':
        ts_Suite = ts_SwitchClassifyPorts()
    elif suite == 'all':
        ts_Suite = unittest.TestSuite((
            ts_FIN(),
            ts_Switchport(),
            ts_SwitchGetInterfaces(),
            ts_SwitchClassifyPorts())
        )
    unittest.TextTestRunner(verbosity=2).run(ts_Suite)
if __name__ == '__main__':
    main()
