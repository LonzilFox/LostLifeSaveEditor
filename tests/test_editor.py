"""Offline regression tests. No user-provided saves are bundled with the repository."""
import copy
import json
from collections import OrderedDict
from pathlib import Path
import struct
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from editor_core import EditorSession, ChangedOnDiskError, describe_diff, collect_leaves
from field_catalog import TOP, get_info
from sol_codec import (SolDocument, parse_sol_bytes, serialize_sol, iter_nodes,
  get_at_path, path_to_text, value_kind, validate_roundtrip, SolError)


def synthetic_doc():
    name='HLB02_Core_1.52'
    prefix=(b'\x00\xbf\x00\x00\x00\x00TCSO\x00\x04\x00\x00\x00\x00'
      + struct.pack('>H',len(name))+name.encode()+b'\x00\x00\x00\x03')
    return SolDocument(name,3,OrderedDict([
        ('DAYS',1),('TopDays',1),('DayHeart',22),('VolumeMaster',0.5),
        ('Mute',False),('Lang','CHT'),('Version','1.52'),
        ('DateLast',OrderedDict([('__type__','date'),('ms',1777777777777.0)])),
        ('LockColor',OrderedDict([('__type__','object'),('__class__',''),
           ('sealed',OrderedDict()),('dynamic',OrderedDict([
             ('swatches',OrderedDict([('__type__','array'),('assoc',OrderedDict()),('dense',[1,0,1,0])]))
           ]))])),
    ]),prefix)


class CodecTests(unittest.TestCase):
    def test_encode_decode(self):
        doc=synthetic_doc()
        raw=serialize_sol(doc)
        d=parse_sol_bytes(raw)
        self.assertEqual(d.entries,doc.entries)
        self.assertEqual(int.from_bytes(raw[2:6],'big'),len(raw)-6)
        self.assertEqual(get_at_path(d.entries,('LockColor','dynamic','swatches','dense',2)),1)
        self.assertEqual(d.entries['DateLast']['ms'],1777777777777.0)
        self.assertTrue(validate_roundtrip(doc)[0])

    def test_type_boundaries(self):
        doc=synthetic_doc()
        doc.entries['DAYS']=0x0FFFFFFF
        self.assertTrue(validate_roundtrip(doc)[0])
        doc.entries['DAYS']=0x10000000  # writer would coerce int to double
        self.assertFalse(validate_roundtrip(doc)[0])

    def test_path_text(self):
        self.assertEqual(path_to_text(('LockColor','dynamic','swatches','dense',3)),'LockColor.swatches[3]')

    def test_catalog_has_user_save_fields(self):
        expected='''VolumeEffect VolumeBGM VolumeVoice Total_Anside Total_Cum Total_Facial myPubes MouseLeftKey HandAlpha MouseRightKey Total_PistonAN autoTypeTouch Total_Tear Total_Mouth Total_Lost ShakeLV Total_Orgsam MainHand MeAlpha LockFilm ViewQuality LockFeel ViewMode LockEye LockCos DateLast LockColor TopDays LockSexM1 sideBoard LockSexD1 MainSide qhelp LockSexFe qrec ViewHeart RecMode Version ShakeMode Lang scaleAutoW scaleAutoF showFPS Reso_F_W Reso_F_H Reso_D_W Reso_D_H DayHeart SCZoomAuto Horny Total_TimeLast Broke Mute DAYS VolumeMaster Agreement VolumeSound Total_Inside Total_Piston'''.split()
        self.assertEqual(len(expected),59)
        self.assertEqual(set(expected),set(TOP))
        self.assertEqual(get_info('LockColor.sox[3]').category,'外观与配色')


class SessionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.folder=Path(self.temp.name)
        self.path=self.folder/'save.sol'
        self.path.write_bytes(serialize_sol(synthetic_doc()))
        self.s=EditorSession()
        self.s.open(self.path)
    def tearDown(self):self.temp.cleanup()

    def test_apply_undo_redo_save_backup(self):
        self.assertEqual(self.s.apply_text(('DAYS',),'98'),1)
        self.assertEqual(self.s.apply_text(('Mute',),'true'),1)
        self.assertEqual(len(self.s.changed_rows()),2)
        self.assertTrue(self.s.undo())
        self.assertIs(self.s.doc.entries['Mute'],False)
        self.assertTrue(self.s.redo())
        self.assertIs(self.s.doc.entries['Mute'],True)
        saved=self.s.save(backup=True)
        self.assertTrue(saved.backup.exists())
        self.assertEqual(parse_sol_bytes(saved.backup.read_bytes()).entries['DAYS'],1)
        self.assertEqual(parse_sol_bytes(self.path.read_bytes()).entries['DAYS'],98)
        self.assertEqual(self.s.changed_rows(),[])

    def test_atomic_revert_on_invalid_edit(self):
        d=self.s.doc
        original=copy.deepcopy(d.entries)
        with self.assertRaises(SolError):
            self.s.apply_text(('DAYS',),'99999999999999999999')
        self.assertEqual(d.entries,original)

    def test_disk_conflict_detected(self):
        self.s.apply_text(('DAYS',),'6')
        self.path.write_bytes(serialize_sol(synthetic_doc())+b'garbage')
        with self.assertRaises(ChangedOnDiskError):self.s.save()
        self.assertTrue(self.path.read_bytes().endswith(b'garbage'))

    def test_json_roundtrip_and_undo(self):
        p=self.folder/'safe-export.json'
        self.s.export_json(p)
        data=json.loads(p.read_text('utf-8'))
        self.assertIsNone(data['source_path'])
        data['entries']['DAYS']=16
        p.write_text(json.dumps(data),encoding='utf-8')
        self.s.import_json(p)
        self.assertEqual(self.s.doc.entries['DAYS'],16)
        self.assertTrue(self.s.undo())
        self.assertEqual(self.s.doc.entries['DAYS'],1)

    def test_structural_diff(self):
        before=synthetic_doc()
        after=synthetic_doc()
        after.entries['LockColor']['dynamic']['swatches']['dense'].append(1)
        rows=describe_diff(before,after)
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['status'],'新增')
        self.assertEqual(rows[0]['path'],'LockColor.swatches[4]')

if __name__=='__main__':unittest.main()
