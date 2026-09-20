from datetime import date
from uuid import uuid4

from database import Context
from models import Customer, CustomerStatus, CustomerStatusEvent


class CustomerRepository:
    def __init__(self, context: Context) -> None:
        self.session = context.db_session

    def create(self, customer_data: dict, password_hash: str) -> Customer:
        customer = Customer()

        customer.name = customer_data["name"]
        customer.email = customer_data["email"]
        customer.document_number = customer_data["document_number"]
        customer.birth_date = date.fromisoformat(customer_data["birthdate"])
        customer.password_hash = password_hash
        customer.customer_key = str(uuid4())
        customer.status_id = self.get_status(CustomerStatus.CREATED).id

        self.session.add(customer)
        return customer

    def update_status(self, customer: Customer, new_status_enumerator: str, reason: str = None) -> None:
        new_status = self.get_status(new_status_enumerator)
        
        new_status_event = CustomerStatusEvent()
        new_status_event.from_status_id = customer.status_id
        new_status_event.to_status_id = new_status.id
        new_status_event.reason = reason
        
        customer.status_id = new_status.id
        customer.status_events.append(new_status_event)

    def get_by_key(self, customer_key: str) -> Customer:
        return self.session.query(Customer).filter(Customer.customer_key == customer_key).first()

    def get_by_document_number(self, document_number: str) -> Customer:
        return self.session.query(Customer).filter(Customer.document_number == document_number).first()

    def get_by_email(self, email: str) -> Customer:
        return self.session.query(Customer).filter(Customer.email == email).first()

    def get_status(self, enumerator: str) -> CustomerStatus:
        return self.session.query(CustomerStatus).filter(CustomerStatus.enumerator == enumerator).one()
