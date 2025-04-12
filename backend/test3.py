import os
import sys


project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
     sys.path.insert(0, project_root)


from reporting.daily_report_generator import generate_daily_report
from datetime import datetime
from datetime import timezone

date_obj = datetime(year = 2023, month = 12, day = 25)

print(generate_daily_report("1d4f2", date_obj))