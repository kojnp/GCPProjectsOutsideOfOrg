import requests
import time
import google.auth.crypt
import google.auth.jwt
import json
import argparse


# STEP 1 Create a JSON Web Token (JWT, pronounced, "jot") which includes a header, a claim set, and a signature.
def generate_jwt(sa_keyfile,
                 sa_email,
                 audience='https://www.googleapis.com/oauth2/v4/token',
                 expiry_length=3600):

    """Generates a signed JSON Web Token using a Google API Service Account."""

    now = int(time.time())

    # build payload
    payload = {
        'iat': now,
        # expires after 'expirary_length' seconds.
        "exp": now + expiry_length,
        # iss must match 'issuer' in the security configuration in your
        # swagger spec (e.g. service account email). It can be any string.
        'iss': sa_email,
        'scope': 'https://www.googleapis.com/auth/cloud-platform',
        # aud must be either your Endpoints service name, or match the value
        # specified as the 'x-google-audience' in the OpenAPI document.
        'aud':  audience,
        # sub and email should match the service account's email address
        'sub': sa_email,
        'email': sa_email
    }

    # sign with keyfile
    signer = google.auth.crypt.RSASigner.from_service_account_file(sa_keyfile)
    jwt = google.auth.jwt.encode(signer, payload)

    return jwt



def get_access_token(signed_jwt, url='https://www.googleapis.com/oauth2/v4/token'):
    headers = {
        'content-type': 'application/x-www-form-urlencoded'
    }
    data = {
        'grant_type': 'urn:ietf:params:oauth:grant-type:jwt-bearer',
        'assertion': signed_jwt
    }
    response = requests.post(url, headers=headers, data=data)

    #response.raise_for_status()
    return response.text

def get_folders_list(access_token, parent_id, url='https://cloudresourcemanager.googleapis.com/v2beta1/folders', parent='folders'):

    params = {
        'access_token': access_token,
        'parent': parent+"/"+parent_id
    }
    response = requests.get(url, params=params)

    #response.raise_for_status()
    return response.text

def recursive_folder_walk(parent_id_string, flag_org_level=False):
    global folder_ids
    global access_token
    folders_json=json.loads(get_folders_list(access_token, parent_id_string, parent='organizations' if flag_org_level else 'folders'))
    if ("folders" in folders_json) :
        for item in folders_json["folders"]:
            folder_id = item["name"].split("/")[1]
            folder_ids += "," + folder_id
            print("folder_id="+folder_id)
            recursive_folder_walk(folder_id, False)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--org_name', help='organization name')
    parser.add_argument('--org_id', help='org id. the script can be modified to retrieve this id itself')
    parser.add_argument('--servacc_email', help='serv account email')
    parser.add_argument('--servacc_json_key_filepath', help='servacc json_key filepath')

    args = parser.parse_args()
    print("Finding folders in org " + args.org_name)

    expiry_length = 3600
    keyfile_jwt = generate_jwt(args.servacc_json_key_filepath, args.servacc_email)
    #print("keyfile_jwt"+keyfile_jwt)
    global access_token
    access_token = json.loads(get_access_token(keyfile_jwt))['access_token']
    #print("access_token="+access_token)

    global folder_ids
    #add ORG id as first element
    folder_ids=args.org_id
    recursive_folder_walk(args.org_id, True)
    print("folder_ids="+folder_ids)
    
    out_file = open(args.org_name+".txt", "w")
    out_file.write(folder_ids)
    out_file.close()