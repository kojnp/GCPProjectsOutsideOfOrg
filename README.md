# Find projects that have an email address in your GSuite domain but are not in your known GCP orgs
For a given email in a GSuite domain, identify GCP projects that have that email having Owner role and are not children of known GCP orgs/folders


## DISCLAIMER: 
1. Any privacy issues are your responsibility. There may be valid reasons for your employees to have Owner role on a GCP project outside of your GCP orgs.
2. This code is not production grade, it was tested only in my test orgs with limited use cases. By running it you accept full responsibility. It may have bugs or expose you in various ways - you accept responsibility.


### Inspiration and source of most important code
[https://medium.com/google-cloud/importing-gcp-projects-into-your-organization-with-python-aa9627bd8f12]
[https://github.com/lukwam/gcp-tools/]


For each user, 3 lists as output:
1) projects without a parent - legacy projects, created before the org node was created
2) projects in other orgs with a confirmed Owner role
3) projects in other orgs for which the Owner role can not be determined. Reason: can have a Owner role set at Folder or Org level but not have Org or Folder getIAM permission, so won't be able to read the IAM policy for that resource. However they do have getIAM on the project.


these were tested with python 2.7


**STEP 1**

I created a serv acc in one project and gave it Org Admin - at org level. Be careful with this serv account and the key. Download JSON key file.

Delete the key after you finish running the script.

For each GCP org you have, run this command:

```
python generate_folder_id_list.py --org_name YOUR_ORG_NAME --org_id YOUR_ORG_ID --servacc_email YOUR_SERVICE_ACCOUNT --servacc_json_key_filepath YOUR_SERVICE_ACOUNT_FILE_PATH_AND_NAME
```

this will create a one line csv file with the list of IDs of your org and all folders it contains


Repeat step 1 for all GCP orgs that you have


**STEP 2**

Service account - reuse that one or create another, your choice. Org admin role. Download JSON key file.

Also needs DwD set up in GSuite Admin console (Security-ADvanced-Manaeg API access)

```
https://www.googleapis.com/auth/admin.directory.user,
https://www.googleapis.com/auth/cloud-platform 
```

See this for more details [https://developers.google.com/identity/protocols/OAuth2ServiceAccount#delegatingauthority]

```
python findProjects.py --nofluff --email EMAIL_OF_PERSON_TO_INVESTIGATE --service_account_json_filepath YOUR_SERV_ACCOUNT_FILE_PATH --folderIDs_filenames SPACE_SEPARATED_FILEPATH_AND_NAME_FOR_FILES_GENERATED_AT_STEP_1
```

If you ommit --nofluff it will generate verbose output.

It will output the 3 lists mentioned in the beginning.



