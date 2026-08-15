


from app.models.orm_models.car_parts_library_bmw import CarPartsLibraryBmw
from app.services.car_parts_library_service.car_parts_library_bmw_service import data_refresh
from app.utils.orm.session import orm_session


def car_parts_library_bmw():
    """
    处理宝马车件库数据
    """
    list_part_numbers = []

    with orm_session() as session:
        # SELECT part_number,part_name,retail_price FROM car_parts_library_bmw WHERE part_name IS NULL LIMIT 5000
        list_part_numbers = session.query(CarPartsLibraryBmw.part_number,
         CarPartsLibraryBmw.part_name, CarPartsLibraryBmw.retail_price).filter(CarPartsLibraryBmw.part_name.is_(None)).limit(5000).all()
        list_part_numbers = [item[0] for item in list_part_numbers]
        print(f"查询到 {len(list_part_numbers)} 条数据")






    # for part_number in list_part_numbers:
    #     print(part_number)

    data_refresh(list_part_numbers)
if __name__ == "__main__":
    for i in range(5):
        car_parts_library_bmw()
