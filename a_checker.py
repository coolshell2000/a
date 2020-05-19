import requests
from datetime import datetime, timedelta, timezone
import time
import os, pathlib, sys
import argparse
import pprint
import json
import pickle
import csv

### EXAMPLE PYTHON MODULE
# Define some variables:

MAX_N_DAYS_PER_PAGE = 6  # max 4, but to sync with bigguy, so 3 days per page

MAX_DAYS_INTO_THE_FUTURE = 14  # 14 is max, Exception is above! to handle

CHECKER_SLEEP_SECONDS_NORMAL = 20

dict_WEEKDAY1to7 = {"sun": 0, "mon": 1 , "tue": 2, "wed": 3, "thu": 4, "fri": 5, "sat": 6}


class Checker:
    def __init__(self, a_type='d'): #, loop_n=1, path_txt_out="out1.txt"):
        self.a_type = a_type
        # self.loop_n = loop_n
        # self.path_txt_out = path_txt_out


    def utc_to_local(self, utc_dt):
        return utc_dt.replace(tzinfo=timezone.utc).astimezone(tz=None)
    
    
    # self restart when modified time is changed for 'path' specified in 'para', default is itself
    # path = pathlib.Path(__file__).absolute()
    # have to privide last_modified_ctime!
    def _self_restart_onchange(self, last_modified_ctime, path=pathlib.Path(__file__).absolute()):
        modified_self = time.ctime(os.path.getmtime(path))
        if modified_self != last_modified_ctime:
            print("modified at {}".format(str(modified_self)))
            # last_modified_ctime = modified_self
            print("_____________________________________________________restarting self...")
            os.execl(sys.executable, sys.executable, *sys.argv)
        # print("self last changed/modified at {}".format( modified_self))
    
    # the 4 days 88 slots via restful api
    # return below 6 paras:
    # ----------------------
    # is_waitclock - True/False
    # a full slot_data(dict!) of this page
    # slot_data_requested_weekdays - filtered by required weekdays
    # reserved_list - 1 or empty
    # time_spent_in_seconds - seconds used for this api call
    def _call_slot88_3days_1page(self, start_dt):
        # array_priority_weekdays_by_n = args.priority
        
        # is_waitclock = False
        # slot_data_requested_weekdays, reserved_list, slot_data = None
        # time_spent_in_seconds = 0
        
        now = datetime.now()
        
        WEEKDAY1to7 = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
        
        url = 'https://groceries.asda.com/api/v3/slot/view'
        
        start_date = start_dt.date().strftime('%Y-%m-%dT%H:%M:%S%z')  # +"+01:00"
        # print(start_date)
        end_date = (start_dt.date() + timedelta(days=MAX_N_DAYS_PER_PAGE)).strftime('%Y-%m-%dT%H:%M:%S%z')  # +"+01:00"
        # print(end_date)
        
        json_params_ok = {
            "data": {
                "customer_info": {
                    "account_id": "5765441" ## changed
                },
                "end_date": end_date,  # "2020-05-21T16:54:09+01:00",
                "order_info": {
                    "line_item_count": 0,
                    "order_id": "12245127612", ### changed
                    "restricted_item_types": [],
                    "sub_total_amount": 0,
                    "total_quantity": 0,
                    "volume": 0,
                    "weight": 0
                },
                "reserved_slot_id": "bcfebb82-6a21-41f2-b13e-f780a7400b0f-2020-05-19",
                "service_address": {
                    "latitude": "50.972785",
                    "longitude": "-1.410298",
                    "postcode": "SO534RE"
                },
                "service_info": {
                    "enable_express": 'false',
                    "fulfillment_type": "DELIVERY"
                },
                "start_date": start_date,  # "2020-05-15T16:54:09+01:00"
            },
            "requestorigin": "gi"
        }
        
        # Make POST request to API, sending required json data
        r = requests.post(url, json=json_params_ok)
        
        # json response
        # pprint.pprint(r.json())
        # sys.exit()
        # Initialise empty dictionary for data
        slot_data = {}
        slot_data_requested_weekdays = {}
        count_soldout = 0
        
        try:
            json_response_slot_day = r.json()['data']['slot_days']
        except Exception as e:
            print("Except e {}".format(str(e)))
            print("wait-clock queuing?")
            # count_waitclock = count_waitclock + 1
            print("(busy api_call/waitclock at {})".format(now.strftime('%a_%H:%M_%d-%b-%Y')))
            now_waitclock = datetime.now()
            time_spent_in_seconds = (now_waitclock - now).microseconds / 1000000
            is_waitclock = True
            slot_data_requested_weekdays = None
            reserved_list = None
            return is_waitclock, slot_data, time_spent_in_seconds, count_soldout+1 / (len(slot_data)+1)  # avoid zero div
            pass  # still need?
        # Loop through json response and record slot status for each time slot
        for slot_day in json_response_slot_day:
            
            slot_date = slot_day['slot_date']
            
            for slot in slot_day['slots']:
                slot_time = slot['slot_info']['start_time']
                slot_time = datetime.strptime(slot_time, '%Y-%m-%dT%H:%M:%SZ')
                
                slot_time = self.utc_to_local(slot_time)
                
                slot_status = slot['slot_info']['status']
                slot_final_price = slot['slot_info']['final_slot_price']
                
                # use slot_time_str as key
                #key = slot_time.strftime('%a_%H:%M_%d-%b-%Y')
                key = slot_time.strftime('%Y-%b-%dT%H:%M_%a')
    
                # 1
                # print("use soldout, RESERVED or final_price as value")
                # if slot_status == "UNAVAILABLE":
                #     slot_data[key] = "soldout"
                if slot_status == "RESERVED":
                    slot_data[key] = "RESERVED"
                elif slot_status == "UNAVAILABLE":
                    slot_data[key] = "UNAVAILABLE"
                    count_soldout = count_soldout + 1
                else:  # AVAILABLE, use price.
                    slot_data[key] = str(slot_final_price)
                
                slot_data["dt_checked"] = now.strftime('%a_%H:%M_%d-%b-%Y')
                
        
        now_finished_api_call = datetime.now()
        time_spent_in_seconds = (now - now_finished_api_call).microseconds / 1000000
        
        is_waitclock = False
        
        perc_soldout = count_soldout / len(slot_data)
        
        return is_waitclock, slot_data, time_spent_in_seconds, perc_soldout
    
    
    def _convert_slot_data_to_panda(self, full_slot_data_dict):
        # print("inside panda for full_slot_data_dict:{}".format(full_slot_data_dict))
        print("inside panda for full_slot_data_dict:")
        pprint.pprint(full_slot_data_dict)
        # 2
        # slot_data's key/value pair is:
        # print("panda construct")
        # author = ['Jitender', 'Purnima', 'Arpit', 'Jyoti']
        # article = [210, 211, 114, 178]
        # auth_series = pd.Series(author)
        # article_series = pd.Series(article)
        # frame = {'Author': auth_series, 'Article': article_series}
        # result = pd.DataFrame(frame)
    
    
    # public method - check the whole range for one time
    # return paras:
    # is_waitclock, slot_data (dt/static inserted)
    def check(self, fullfill_type='d'):
        full_dict_slot_data = {}
        array_of_reserved_list = []
        
        page_current = 0
        is_waitclock = False
        full_dict_slot_data = {}
        perc_soldout_avg = 1
        
        dt_start = datetime.now()
        pagings = range(0, MAX_DAYS_INTO_THE_FUTURE, MAX_N_DAYS_PER_PAGE)  # 0,3,6,9,12
        for days_into_future in pagings:
            array_of_reserved_list = []
            page_current += 1
    
            ts_now = datetime.now()
            
            start_dt_as_date = ts_now + timedelta(days=days_into_future)
            #end_dt_as_date = start_dt_as_date + timedelta(days=MAX_N_DAYS_PER_PAGE)
            
            is_waitclock, slot_data_this_page, time_spent_in_seconds, perc_soldout = \
                self._call_slot88_3days_1page(start_dt=start_dt_as_date)
            if is_waitclock:
                perc_soldout = 1  # assume 100% soldout if queue/busy
            
            # print("perc_soldout:{:.02f}".format(perc_soldout))
            if days_into_future == 0:
                perc_soldout_avg_sum = perc_soldout
            else:
                perc_soldout_avg_sum = perc_soldout_avg_sum + perc_soldout
            
            if is_waitclock:
                # may return an empty or partial dict
                is_waitclock = True
                print("restful api busy... sleep 5")
                time.sleep(5)
                continue  # might be empty full_slot_list this round due to waitclock/busyqueue. next around
            else:
                # concat/merge dict! # not array list
                full_dict_slot_data.update(slot_data_this_page)
    
            if len(array_of_reserved_list) > 0:
                for reserved_list in array_of_reserved_list:  # all reserved_list in this round (multiple pages)
                    print("{}".format(reserved_list))
            
            time.sleep(0.1)
    
        perc_soldout_avg = perc_soldout_avg_sum / len(pagings)
        full_dict_slot_data["perc_soldoout"] = "{:.1f}%".format(perc_soldout_avg*100)
        
        now = datetime.now()
        full_dict_slot_data["dt_checked"] = now.strftime('%a_%H:%M_%d-%b-%Y')
        full_dict_slot_data["cost_in_seconds"] = (now-dt_start).seconds
    
        return is_waitclock, full_dict_slot_data
        
    
    def loop(self, loop_n):
        
        path_self = pathlib.Path(__file__).absolute()
        last_modified_ctime_self = time.ctime(os.path.getmtime(path_self))
        
        path_pickle_stats = "out1_stats.pickle"
        path_txt_out = "out1.txt"
        
    
    
        ts_start = datetime.now()
        
        # count_all_soldout = 0
        # count_waitclock = 0
        #
        # counter_api_call = 0
    
        # if os.path.exists(path_pickle_stats):
        #     pickle_in = open(path_pickle_stats, "rb")
        #     d_stats_avg = pickle.load(pickle_in)
        #     pickle_in.close()
        # else:
        #     d_stats_avg[]
        
        perc_soldoout_avg_sofar = None
        
        for loop_i in range(0, loop_n):
            # print("***********************************************")
            # print("******************NEW LOOP*********************")
            # print("***********************************************")
    
    
            full_dict_slot_data = {}
            array_of_reserved_list = []
            
            # relaunch if self changed
            self._self_restart_onchange(last_modified_ctime_self, path=path_self)
            
            is_waitclock, full_dict_slot_data = self.check(args.type[0])
    
            
            d_stats = {}
            d_stats['cost_in_seconds'] = full_dict_slot_data['cost_in_seconds']
            d_stats['dt_checked'] = full_dict_slot_data['dt_checked']
            d_stats['perc_soldoout'] = full_dict_slot_data['perc_soldoout']
            if loop_i == 0:
                perc_soldoout_avg_sofar = float(d_stats['perc_soldoout'].strip('%'))/100
            else:
                perc_soldoout_avg_sofar = (perc_soldoout_avg_sofar + float(d_stats['perc_soldoout'].strip('%'))/100)/(loop_i+1)
                full_dict_slot_data['perc_soldoout_avg_sofar'] = str(perc_soldoout_avg_sofar*100)+"%"
            
            with open(path_txt_out, "w") as f:
                w = csv.writer(f)
                for key in sorted(full_dict_slot_data.keys()):
                    # for val in full_dict_slot_data[key]:
                    w.writerow([key, full_dict_slot_data[key]])
            f.close()
            
    
            pprint.pprint(full_dict_slot_data)
    
            ts_now = datetime.now()
            duration_in_minutes = (ts_now - ts_start).seconds / 60
            print("\nduration_in_minutes:{:.1f}".format(duration_in_minutes))
            
            if loop_i+1 < args.loop_n[0]:
                print("\nsleep {} seconds..".format(CHECKER_SLEEP_SECONDS_NORMAL))
                time.sleep(CHECKER_SLEEP_SECONDS_NORMAL)
            



if __name__ == '__main__':
    parser = argparse.ArgumentParser()  # (description='grabbing slots')
    
    parser.add_argument('type', type=str, nargs=1, choices=["d", "c"],
                        help='specify  d:delivery or c:c_c')
    parser.add_argument('-loop_n', type=int, nargs=1,
                        choices=[1, 2] + list(range(60, int(8 * 3600 / CHECKER_SLEEP_SECONDS_NORMAL), 60)), default=[1],
                        help='max number of scans/loops, maxs is a number calculated for 8 hours')
    
    args = parser.parse_args()

    checker = Checker(args.type)#, args.loop_n, path_txt_out)

    checker.loop(args.loop_n[0])
