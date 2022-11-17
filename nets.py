#!/usr/bin/env python3
"""
This script reads network objects from a CSV file and add the missing networks
to a predefined group using the management API.

network,description
120.190.200.0/24,"internal Net"
151.100.111.0/24,"Azure Net"

install the Check Point SDK using
pip install cp-mgmt-api-sdk
"""

import sys
import csv
from cpapi import APIClient, APIClientArgs


def main():
    api_server = "203.0.113.120"
    username = "admin"
    password = "Cpwins!1"
    group_name = "example_group"
    csv_filename = "src_nets.csv" #sys.argv[1]#
    session_name = "add csv example session" 
    session_description = "description added using script"
    
    # read the csv file src_nets.csv from current location.
    with open(csv_filename) as csvfile:
        net_list = []
        csv_reader = csv.DictReader(csvfile)
        for row in csv_reader:
            net_list.append(row)

    client_args = APIClientArgs(server=api_server)
    with APIClient(client_args) as client:

        login = client.login(username, password)

        if not login.success:
            print(login.error_message)
            sys.exit(1)

        # pull existing nets from the defined group
        nets = client.api_call("show-group",
                               payload={
                                   "name": group_name,
                                   "details-level": "Full"
                               })
        
        if not nets.success:
            print(nets.error_message)
            client.api_call("discard")
            sys.exit(1)
                            
        # add mask length to the subnet (e.g. 10.0.0.0 to 10.0.0.0/24)
        converted_nets = []
        members = []
        existing_members = []

        for net in nets.data["members"]:
            subnet = str(net["subnet4"]) + "/" + str(net["mask-length4"])
            converted_nets.append(subnet)
            existing_members.append(net["name"])
        if [item["network"] for item in net_list] == converted_nets:
            print("Group members are matching the CSV entries. Exiting.")
            client.api_call("logout")
            sys.exit(0)
            
        # Add the network if it doesn't exist on the management.
        for item in net_list:
            network_address, mask_length = item["network"].split("/")

            # changin naming convension, add zeros if needed
            octets = [
                f"{int(octet):03}" for octet in network_address.split(".")
            ]

            network_name = "Net-" + ".".join(octets) + f"-{mask_length}"
            description = item["description"]
            members.append(network_name)

            if item["network"] in converted_nets:
                print(
                    f"subnet {item['network']} exists on the management station"
                )


            else:
                print(
                    f"subnet {item['network']} does not exist in the group {group_name}, we must add it to the Mgmt {item['network']}."
                )

                # check if the network already exists even if not part of the group.
                check_network_duplicate = client.api_call(
                    "show-network",
                    payload={
                        "name": network_name,
                        "details-level": "Full"
                    })

                if check_network_duplicate.success:
                    net_name = check_network_duplicate.data["name"]
                    net_address = check_network_duplicate.data["subnet4"]
                    net_mask_length = check_network_duplicate.data[
                        "mask-length4"]
                    net_comments = check_network_duplicate.data["comments"]

                    if net_name != network_name or net_address != network_address or net_mask_length != mask_length or net_comments != description:
                        update_network = client.api_call(
                            "set-network",
                            payload={
                                "name": network_name,
                                "subnet": network_address,
                                "mask-length4": mask_length,
                                "comments": description
                            })
                        if not update_network.success:
                            print(update_network.error_message)
                            client.api_call("discard")
                            sys.exit(1)


                elif check_network_duplicate.data[
                        "code"] == "generic_err_object_not_found":

                    # create the network object if it doesn't exist
                    add_network = client.api_call(
                        "add-network",
                        payload={
                            "name": network_name,
                            "subnet": network_address,
                            "mask-length4": mask_length,
                            "comments": description
                        })
                    if not add_network.success:
                        print(add_network.error_message)
                        client.api_call("discard")
                        sys.exit(1)
                    # make a list of members
                    print(network_name)

                else:
                    print(check_network_duplicate.error_message)
                    sys.exit(1)
        to_be_removed = set(existing_members) - set(members) 
        if to_be_removed:
            print(f"Removing: {to_be_removed}")
        # update the group by adding the missing network
        add_network_to_group = client.api_call("set-group",
                                               payload={
                                                   "name": group_name,
                                                   "members": members
                                               })
        if not add_network_to_group.success:
            print(add_network_to_group.error_message)
            sys.exit(1)
        
        print("Setting session name and description...")
        set_session = client.api_call("set-session", payload={"new-name": session_name, "description": session_description})
        if not set_session.success:
            print(set_session.error_message)
            
        print("Publishing changes...")
        publish = client.api_call("publish")
        if not publish.success:
            print(publish.error_message)
        print("Published changes, please install policy.")


if __name__ == "__main__":
    main()
