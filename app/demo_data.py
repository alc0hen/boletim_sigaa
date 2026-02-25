import json
def get_demo_data():
    """
    Generator that yields demo data messages similar to the real SIGAA stream.
    Now yields raw-like grade structures for the backend calculator.
    """
    yield {
        "type": "user_info",
        "name": "Aluno Demonstração",
        "is_supporter": True
    }
    c1_id = 1
    yield {
        "type": "course_start",
        "id": c1_id,
        "name": "Matemática Aplicada",
        "obs": "Técnico em Informática"
    }
    yield {
        "type": "course_data",
        "id": c1_id,
        "data": [
            {'name': 'Unidade 1', 'type': 'group', 'grades': [{'name': 'Nota', 'value': 10.0}]},
            {'name': 'Unidade 2', 'type': 'group', 'grades': [{'name': 'Nota', 'value': 9.5}, {'name': 'Nota', 'value': 10.0}]},
            {'name': 'Unidade 3', 'type': 'group', 'grades': [{'name': 'Nota', 'value': 10.0}]},
            {'name': 'Unidade 4', 'type': 'group', 'grades': [{'name': 'Nota', 'value': 9.0}]}
        ]
    }
    yield {
        "type": "course_frequency",
        "id": c1_id,
        "data": {
            "total_faltas": 2,
            "max_faltas": 20,
            "percent": 2.5
        }
    }
    c2_id = 2
    yield {
        "type": "course_start",
        "id": c2_id,
        "name": "Física I",
        "obs": "Técnico em Informática"
    }
    yield {
        "type": "course_data",
        "id": c2_id,
        "data": [
            {'name': 'Unidade 1', 'type': 'group', 'grades': [{'name': 'Nota', 'value': 4.0}, {'name': 'Nota', 'value': 3.5}]},
            {'name': 'Unidade 2', 'type': 'group', 'grades': [{'name': 'Nota', 'value': 5.0}]},
            {'name': 'Unidade 3', 'type': 'group', 'grades': [{'name': 'Nota', 'value': 6.0}, {'name': 'Nota', 'value': 5.5}]},
            {'name': 'Unidade 4', 'type': 'group', 'grades': [{'name': 'Nota', 'value': 4.0}]},
            {'name': 'Recuperação 1', 'value': 7.5, 'type': 'single'}
        ]
    }
    yield {
        "type": "course_frequency",
        "id": c2_id,
        "data": {
            "total_faltas": 12,
            "max_faltas": 20,
            "percent": 15.0
        }
    }
    c3_id = 3
    yield {
        "type": "course_start",
        "id": c3_id,
        "name": "Programação Web",
        "obs": "Técnico em Informática"
    }
    yield {
        "type": "course_data",
        "id": c3_id,
        "data": [
            {'name': 'Unidade 1', 'type': 'group', 'grades': [{'name': 'Nota', 'value': 8.0}]},
            {'name': 'Unidade 2', 'type': 'group', 'grades': [{'name': 'Nota', 'value': 7.5}]},
            {'name': 'Unidade 3', 'type': 'group', 'grades': [{'name': 'Nota', 'value': 8.0}]},
            {'name': 'Unidade 4', 'type': 'group', 'grades': [{'name': 'Nota', 'value': 9.0}]}
        ]
    }
    yield {
        "type": "course_frequency",
        "id": c3_id,
        "data": {
            "total_faltas": 25,
            "max_faltas": 20,
            "percent": 31.2
        }
    }
    c4_id = 4
    yield {
        "type": "course_start",
        "id": c4_id,
        "name": "Língua Portuguesa",
        "obs": "Técnico em Informática"
    }
    yield {
        "type": "course_data",
        "id": c4_id,
        "data": [
            {'name': 'Unidade 1', 'type': 'group', 'grades': [{'name': 'Nota', 'value': 7.0}]},
            {'name': 'Unidade 2', 'type': 'group', 'grades': [{'name': 'Nota', 'value': 6.5}]},
            {'name': 'Unidade 3', 'type': 'group', 'grades': [{'name': 'Nota', 'value': 8.0}]},
            {'name': 'Unidade 4', 'type': 'group', 'grades': []}
        ]
    }
    yield {
        "type": "course_frequency",
        "id": c4_id,
        "data": {
            "total_faltas": 8,
            "max_faltas": 20,
            "percent": 10.0
        }
    }
