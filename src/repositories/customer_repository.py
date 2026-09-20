from datetime import date
from uuid import uuid4

from database import Context
from models import Customer, CustomerStatus, CustomerStatusEvent


class CustomerRepository:
    """A camada que fala com o banco. Só aqui existe query.

    Nenhuma regra de negócio mora aqui: esta classe busca, guarda e
    atualiza — quem decide o que fazer com isso é o controller.

    É assim nos serviços da QI, e a linha é a mesma lá e aqui:
    `self.session = context.db_session`.
    """

    def __init__(self, context: Context) -> None:
        self.session = context.db_session

    def create(self, customer_data: dict, password_hash: str, birth_date: date) -> Customer:
        customer = Customer()

        customer.name = customer_data["name"]
        customer.email = customer_data["email"]
        customer.document_number = customer_data["document_number"]
        customer.birth_date = birth_date
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

    def list_page(self, limit: int, offset: int, filters: dict) -> list[Customer]:
        query = self.session.query(Customer)

        status_enumerators = filters.get("status_enumerators")
        if status_enumerators:
            query = query.join(Customer.status).filter(CustomerStatus.enumerator.in_(status_enumerators))

        name = filters.get("name")
        if name is not None:
            query = query.filter(Customer.name.ilike(f"%{name}%"))

        email = filters.get("email")
        if email is not None:
            query = query.filter(Customer.email == email)

        document_number = filters.get("document_number")
        if document_number is not None:
            query = query.filter(Customer.document_number == document_number)
    
        query = query.order_by(Customer.created_at.desc(), Customer.id.desc())

        return query.limit(limit + 1).offset(offset).all()
