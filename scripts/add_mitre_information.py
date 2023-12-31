import json
import ssl
from bs4 import BeautifulSoup
import demisto_client.demisto_api
from demisto_client.demisto_api.rest import ApiException
import requests

print('''
########################################################################################################################
                                                                                                           
\tThis script adds known MITRE ATT&CK information to the Cortex XSOAR indicators specified in the          
\tentries setting. It uses the aliases field to find the record, so make sure, that each of the entries from
\tthe configuration file is contained as alias in Cortex only once. 
\tUse the count_records_alias.py script to check.                                                                                    
\tThe script checks the MITRE webpage for groups and software and if it finds the value from entries there, it
\tadds all known techniques, aliases and a description if the latter is not yet available in Cortex.    
\n\t!! Data will only be overwritten in Cortex after confirmation.                                         
\tYou can still decide for each single entry whether it should be updated or not !!                                               
                                                                                                           
\t(c) 2023 Sandra Liedtke.                                                                                 
                                                                                                          
########################################################################################################################
''')
cont = input("Want to continue (Yes/No)? ")
print('\n')


if cont.upper() in ["Y", "YES"]:
    # own function, so it can be called multiple times without redundant code
    def check_aliases():
        # if there are any aliases on the Mitre webpage, add them to the record in Cortex
        if table_data[2].text.replace('\n', '').strip() != '':
            for alias in aliases.split(','):
                if alias not in ioc_object.custom_fields['aliases']:
                    ioc_object.custom_fields['aliases'].append(alias)
        # add the name from Mitre if the record is found as an alias
        if indicator_name.upper() != match.upper():
            is_alias = False
            for alias in ioc_object.custom_fields['aliases']:
                if match.upper() == alias.upper():
                    is_alias = True
            if not is_alias:
                ioc_object.custom_fields['aliases'].append(match)


    # get config
    with open('../config/config.json', 'r') as config_file:
        CONFIG = json.load(config_file)

    # technical name of the field where the mitre attack techniques should be added
    mitre_field_name = "mitreattacktechnique"
    continue_ = input("Found MITRE ATT&CK Techniques will be entered to the field custom_fields." + mitre_field_name + "\n\nTHIS MAY OVERWRITE EXISTING VALUES IN CORTEX XSOAR!\nDo you want to continue and replace existing data (Y/n)? ")

    if continue_.upper() in ["Y", "YES"]:
        print("Further information will be added to the fields custom_fields.aliases and/or custom_fields.description. The description field will not be overwritten if it already has values in Cortex XSOAR")
        # api instance
        api_instance = demisto_client.configure(base_url=CONFIG['CortexXSOARAPIConfig']['host'], debug=False, verify_ssl=ssl.CERT_NONE, api_key=CONFIG['CortexXSOARAPIConfig']['api_key'])

        # call mitre webpage
        user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/70.0.3538.102 Safari/537.36'
        headers = {'User-Agent': user_agent}
        try:
            # send get request to MITRE
            print("Getting known groups from MITRE...")
            groups = requests.get("https://attack.mitre.org/groups/", headers=headers)
            print("Getting known software from MITRE...")
            sw = requests.get("https://attack.mitre.org/software/", headers=headers)
        except Exception as e:
            print('Error accessing webpage. Error Message: ', str(e))
            exit()

        # only the table and its rows
        g_website_content = BeautifulSoup(groups.content, 'html.parser')
        g_table_body = g_website_content.find('tbody')
        g_rows = g_table_body.find_all('tr')
        sw_website_content = BeautifulSoup(sw.content, 'html.parser')
        sw_table_body = sw_website_content.find('tbody')
        sw_rows = sw_table_body.find_all('tr')
        mitre_webpage = g_rows
        mitre_webpage += sw_rows
        # for each entry
        for indicator_name in CONFIG['entries']:
            for tr in mitre_webpage:
                table_data = tr.find_all('td')
                # match the name in the second and third column
                match = table_data[1].text.replace ('\n', '').strip()
                aliases = table_data[2].text.replace ('\n', '')
                if (indicator_name.upper() in match.replace(' ', '').upper()) or (indicator_name.upper() in aliases.replace(' ', '').upper()):
                    try:
                        # search current record in Cortex
                        indicator_filter = demisto_client.demisto_api.IndicatorFilter()
                        indicator_filter.query = 'aliases:"' + indicator_name + '"'
                        found_indicator = api_instance.indicators_search(indicator_filter=indicator_filter)
                        # if the record exists in Cortex re-verify before updating it
                        if found_indicator.total == 1:
                            print("\n\nFound " + indicator_name.upper() + " in mitre row " + match.upper() + " with Aliases " + aliases.strip().upper())
                            print("The record does also exist in Cortex")
                            go_on = input("Continue overwriting Cortex values with mitre values (Y,n)? ")
                            if go_on.upper() in ["Y", "YES"]:
                                # get respective MITRE techniques without subtechniques from webpage
                                page = requests.get('https://attack.mitre.org' + table_data[1].contents[1].attrs['href'], headers=headers)
                                parsed_page = BeautifulSoup(page.content, 'html.parser')
                                tech_table = parsed_page.find('table', {"class": "table techniques-used background table-bordered"})
                                techniques = tech_table.find('tbody')
                                tech_rows = techniques.find_all('tr')
                                techniques = []
                                for row in tech_rows:
                                    td = row.find_all('td')
                                    text = td[3].text.split(':')[0] if ':' in td[3].text else td[2].text
                                    techniques.append(text.replace('\n', ''))
                                # indicator exists -> update it
                                ioc_object = demisto_client.demisto_api.IocObject(found_indicator.ioc_objects[0])
                                # Mapping of existing values
                                ioc_object.custom_fields = found_indicator.ioc_objects[0]['CustomFields']
                                ioc_object.calculated_time = found_indicator.ioc_objects[0]['calculatedTime']
                                ioc_object.first_seen = found_indicator.ioc_objects[0]['firstSeen']
                                ioc_object.first_seen_entry_id = found_indicator.ioc_objects[0]['firstSeenEntryID']
                                ioc_object.id = found_indicator.ioc_objects[0]['id']
                                ioc_object.indicator_type = found_indicator.ioc_objects[0]['indicator_type']
                                ioc_object.last_seen = found_indicator.ioc_objects[0]['lastSeen']
                                ioc_object.last_seen_entry_id = found_indicator.ioc_objects[0]['lastSeenEntryID']
                                ioc_object.modified = found_indicator.ioc_objects[0]['modified']
                                ioc_object.score = found_indicator.ioc_objects[0]['score']
                                ioc_object.sort_values = found_indicator.ioc_objects[0]['sortValues']
                                ioc_object.timestamp = found_indicator.ioc_objects[0]['timestamp']
                                ioc_object.value = found_indicator.ioc_objects[0]['value']
                                ioc_object.version = found_indicator.ioc_objects[0]['version']
                                # append mitre attack techniques
                                ioc_object.custom_fields['mitreattacktechnique'] = techniques
                                # add aliases and description if they exist in MITRE and do not exist in Cortex
                                try:
                                    check_aliases()
                                except:
                                    # field does not exist - create it first
                                    ioc_object.custom_fields['aliases'] = []
                                    check_aliases()
                                try:
                                    if ioc_object.custom_fields['description'] == '' or 'description' not in ioc_object.custom_fields.keys():
                                        ioc_object.custom_fields['description'] = table_data[3].text.replace('\n', '').strip()
                                except:
                                    ioc_object.custom_fields['description'] = table_data[3].text.replace('\n', '').strip()
                                # the actual API-Request
                                try:
                                    api_response = api_instance.indicators_edit(ioc_object=ioc_object)
                                    print("Updated " + indicator_name + " in Cortex XSOAR")
                                except ApiException as e:
                                    print("Error while writing " + indicator_name + " to Cortex XSOAR")
                                    print(e)
                    # catch exceptions
                    except ApiException as e:
                        print(e)
                        print("Skipping XSOAR Archiving for " + indicator_name)
