
from datetime import datetime
from pytz import timezone
import pytz

date_format='%m/%d/%Y %H:%M:%S %Z'
date = datetime.now(tz=pytz.utc)
print( 'Current date & time is:', date.strftime(date_format))

date = date.astimezone(timezone('US/Pacific'))
print( 'Local date & time is  :', date.strftime(date_format))


current = datetime.now(tz=pytz.utc)
print("current: ", current)


current = current.astimezone(timezone('US/Pacific'))
print("current2: ", current)
print( 'Local date & time is  :', current.strftime(date_format))