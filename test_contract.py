import hashlib
import importlib.util
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch


runtime = ModuleType("genlayer")
runtime.u64 = int
runtime.TreeMap = dict
runtime.gl = SimpleNamespace(
    Contract=object,
    public=SimpleNamespace(write=lambda fn: fn, view=lambda fn: fn),
    eq_principle=SimpleNamespace(strict_eq=lambda observe: observe()),
    nondet=SimpleNamespace(web=SimpleNamespace(request=None)),
    UserError=ValueError,
)
spec = importlib.util.spec_from_file_location("transit_contract", Path(__file__).with_name("contract.py"))
contract = importlib.util.module_from_spec(spec)
with patch.dict(sys.modules, {"genlayer": runtime}):
    spec.loader.exec_module(contract)


class TransitTests(unittest.TestCase):
    def setUp(self):
        self.body = Path(__file__).with_name("schedule.json").read_bytes()
        self.app = contract.TransitWitness()
        self.app.records = {}
        self.app.query_ids = {}

    def test_transfer_buffer_and_deadline(self):
        rows = contract.parse_schedule(self.body)
        def travel(buffer, legs):
            return contract.solve(rows, "Library", "Airport", 1370, 1470, buffer, legs)
        self.assertEqual(travel(5, 2)["legs"], ["T1", "T3"])
        self.assertEqual(travel(3, 2)["arrival"], 1450)
        self.assertEqual(travel(5, 1)["status"], "NO_ROUTE_IN_SNAPSHOT")

    def test_bad_input_and_replayed_query(self):
        digest = hashlib.sha256(self.body).hexdigest()
        def attest(expected):
            return self.app.attest("example", "transit", "a" * 40, expected,
                                   "Library", "Airport", 1370, 1470, 5, 2)
        with patch.object(runtime.gl.nondet.web, "request", return_value=SimpleNamespace(status=200, body=self.body)) as request:
            with self.assertRaisesRegex(ValueError, "digest mismatch"):
                attest("0" * 64)
            self.assertEqual(self.app.count, 0)
            self.assertEqual(attest(digest), 1)
            self.assertEqual(attest(digest), 1)
            self.assertEqual(request.call_count, 2)
            self.assertIn("T3", self.app.get_attestation(1))

    def test_early_arrival_with_more_legs_does_not_hide_direct_connection(self):
        rows = [["first", "A", "B", 0, 3], ["second", "B", "C", 3, 5],
                ["direct", "A", "C", 0, 8], ["last", "C", "D", 9, 12]]
        result = contract.solve(rows, "A", "D", 0, 13, 0, 2)
        self.assertEqual(result["legs"], ["direct", "last"])

    def test_duplicate_and_boolean_times_are_rejected(self):
        for body in [
            b'{"schema":"transit-witness/v1","legs":[["T","A","B",0,1],["T","B","C",1,2]]}',
            b'{"schema":"transit-witness/v1","legs":[["T","A","B",false,1]]}',
        ]:
            with self.assertRaises(AssertionError):
                contract.parse_schedule(body)
