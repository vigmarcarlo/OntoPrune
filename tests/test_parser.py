"""
Unit tests for ontoprune.parser.
"""

from pathlib import Path

from rdflib import RDF, RDFS, Literal, Namespace

from ontoprune.parser import parse_file, parse_source

SOFT = Namespace("https://w3id.org/ontoprune/software#")
REPO = Namespace("https://w3id.org/ontoprune/repo/")


def test_parse_simple_source() -> None:
    code = """
class Calculator:
    \"\"\"Basic math calculator.\"\"\"
    def add(self, a: int, b: int = 0) -> int:
        return a + b
"""
    g = parse_source(code, module_name="calc")

    # Module
    mod_uri = REPO["module_calc"]
    assert (mod_uri, RDF.type, SOFT.Module) in g

    # Class
    cls_uri = REPO["class_Calculator"]
    assert (cls_uri, RDF.type, SOFT.Class) in g
    assert (cls_uri, RDFS.label, Literal("Calculator")) in g
    assert (mod_uri, SOFT.containsClass, cls_uri) in g

    # Method
    func_uri = REPO["func_Calculator.add"]
    assert (func_uri, RDF.type, SOFT.Function) in g
    assert (cls_uri, SOFT.hasMethod, func_uri) in g
    assert (func_uri, SOFT.belongsToClass, Literal("Calculator")) in g
    assert (func_uri, SOFT.returnsType, Literal("int")) in g

    # Parameters
    param_a = REPO["param_Calculator.add_a"]
    param_b = REPO["param_Calculator.add_b"]
    assert (func_uri, SOFT.hasParameter, param_a) in g
    assert (func_uri, SOFT.hasParameter, param_b) in g
    assert (param_a, SOFT.hasType, Literal("int")) in g
    assert (param_b, SOFT.hasDefault, Literal("0")) in g


def test_no_uri_collision_between_methods_with_same_name() -> None:
    """Verify G1: methods with identical names in different classes have unique URIs."""
    code = """
class ServiceA:
    def save(self, data: str) -> bool:
        return True

class ServiceB:
    def save(self, record_id: int) -> None:
        pass
"""
    g = parse_source(code, "test_g1")

    uri_a = REPO["func_ServiceA.save"]
    uri_b = REPO["func_ServiceB.save"]

    assert uri_a != uri_b
    assert (uri_a, RDF.type, SOFT.Function) in g
    assert (uri_b, RDF.type, SOFT.Function) in g
    assert (uri_a, SOFT.belongsToClass, Literal("ServiceA")) in g
    assert (uri_b, SOFT.belongsToClass, Literal("ServiceB")) in g


def test_sample_service_fixture_parsing() -> None:
    fixture_path = Path(__file__).parent.parent / "fixtures" / "sample_service.py"
    assert fixture_path.exists(), "sample_service.py fixture must exist"

    g = parse_file(fixture_path, module_name="sample_service")

    # Check OrderService and procesar_orden
    order_svc_cls = REPO["class_OrderService"]
    procesar_func = REPO["func_OrderService.procesar_orden"]

    assert (order_svc_cls, RDF.type, SOFT.Class) in g
    assert (procesar_func, RDF.type, SOFT.Function) in g
    assert (order_svc_cls, SOFT.hasMethod, procesar_func) in g
    ret_type = str(g.value(procesar_func, SOFT.returnsType))
    assert ret_type in {"Invoice | None", "Optional[Invoice]"}

    # Invocations from procesar_orden:
    # 1. self.validar_orden -> func_OrderService.validar_orden
    # 2. self.inventory_service.reservar_stock -> func_InventoryService.reservar_stock
    # 3. self.payment_gateway.cobrar -> func_PaymentGateway.cobrar
    # 4. self.billing_service.emitir_factura -> func_BillingService.emitir_factura
    # 5. self.order_repo.update_status -> func_OrderRepository.update_status
    invoked = set(g.objects(procesar_func, SOFT.invokes))

    assert REPO["func_OrderService.validar_orden"] in invoked
    assert REPO["func_InventoryService.reservar_stock"] in invoked
    assert REPO["func_PaymentGateway.cobrar"] in invoked
    assert REPO["func_BillingService.emitir_factura"] in invoked
    assert REPO["func_OrderRepository.update_status"] in invoked


def test_dataclass_and_domain_type_parsing() -> None:
    code = """
from dataclasses import dataclass

@dataclass
class Customer:
    id: str
    email: str

class CustomerService:
    def get_customer(self, customer_id: str) -> Customer:
        pass
"""
    g = parse_source(code, "test_dataclass")
    cust_uri = REPO["class_Customer"]
    assert (cust_uri, RDF.type, SOFT.Class) in g
    assert (cust_uri, SOFT.decoratedWith, Literal("dataclass")) in g

    attr_id = REPO["attr_Customer_id"]
    assert (cust_uri, SOFT.hasAttribute, attr_id) in g
    assert (attr_id, SOFT.hasType, Literal("str")) in g

    func_uri = REPO["func_CustomerService.get_customer"]
    assert (func_uri, SOFT.usesType, cust_uri) in g

