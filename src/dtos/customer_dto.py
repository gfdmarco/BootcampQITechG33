from typing import List
from models import Customer


class CustomerDTO:
    @staticmethod
    def obj_to_dict(customer: Customer) -> dict:
        customer_dto = CustomerDTO.obj_to_simplified_dict(customer)
        customer_dto["status_events"] = []

        for status_event in customer.status_events:
            status_event_dto = dict()
            status_event_dto["status"] = status_event.to_status.enumerator
            status_event_dto["event_datetime"] = status_event.created_at.isoformat()
            if status_event.reason:
                status_event_dto["reason"] = status_event.reason

            customer_dto["status_events"].append(status_event_dto)

        return customer_dto

    @staticmethod
    def obj_to_simplified_dict(customer: Customer) -> dict:
        dto = dict()
        dto["customer_key"] = customer.customer_key
        dto["name"] = customer.name
        dto["email"] = customer.email
        dto["document_number"] = customer.document_number
        dto["birthdate"] = customer.birth_date.isoformat()
        dto["status"] = customer.status.enumerator
        return dto

    @staticmethod
    def list_obj_to_list_dict(customers_list: List[Customer]) -> List[dict]:
        customers_dict_list = []

        for customer in customers_list:
            customers_dict_list.append(CustomerDTO.obj_to_simplified_dict(customer))

        return customers_dict_list
