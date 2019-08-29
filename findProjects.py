import argparse
import re
import sys
import chardet

from googleapiclient.discovery import build
from oauth2client.service_account import ServiceAccountCredentials

# Email of the Service Account
SERVICE_ACCOUNT_EMAIL = 'XXXXXXXXXXXXXXXXXXXXXXXXXX'

# Path to the Service Account's Private Key file
SERVICE_ACCOUNT_PKCS12_FILE_PATH = 'XXXXXXXXXXXXXXXXXXXXXXXXXX'
SERVICE_ACCOUNT_JSON_FILE_PATH = 'XXXXXXXXXXXXXXXXXXXXXXXXXX'
SERVICE_ACCOUNT_NOT_AUTHORIZED_JSON_FILE_PATH = 'XXXXXXXXXXXXXXXXXXXXXXXXXX'
inscopeprojects = {}
projectsInOtherOrgsConfirmedOwner = []
projectsInOtherOrgsUnconfirmedRole = []

def buildapiservices(user_email, service_acc_filepath):
    """Build and returns an Admin SDK Directory service object authorized with the service accounts
    that act on behalf of the given user.

    Args:
      user_email: The email of the user. Needs permissions to access the Admin APIs.
    Returns:
      Admin SDK directory service object.
    """
    global directory
    global crm
    global crm_v2beta1
    #credentials = ServiceAccountCredentials.from_p12_keyfile(
    credentials = ServiceAccountCredentials.from_json_keyfile_name(
    #    SERVICE_ACCOUNT_EMAIL,
    #    SERVICE_ACCOUNT_PKCS12_FILE_PATH,
    #     SERVICE_ACCOUNT_JSON_FILE_PATH,
        service_acc_filepath,
    ##     SERVICE_ACCOUNT_NOT_AUTHORIZED_JSON_FILE_PATH,
    #    'notasecret',
        scopes=['https://www.googleapis.com/auth/admin.directory.user',
            'https://www.googleapis.com/auth/cloud-platform',])

    credentials = credentials.create_delegated(user_email)

    directory = build('admin', 'directory_v1', credentials=credentials)

    crm = build('cloudresourcemanager','v1',credentials=credentials)
    crm_v2beta1 = build('cloudresourcemanager','v2beta1',credentials=credentials)

def checkOwner(email,project_id):
    params = {
        'resource': project_id,
        'body': {},
    }

    owner = None
    bindings = None
    
    try:
        # retrieve the iam policy for the project
        policy = crm.projects().getIamPolicy(**params).execute()

        # scan each of the bindings to see if user is owner
        bindings = policy.get('bindings', [])
        for b in bindings:

            # skip bindings other than owner
            if b['role'] != 'roles/owner':
                continue

            printThis("This project's owners:"+str(b['members']))

            # see if user is one of the owners
            if 'user:%s' % (email) in b['members']:
                owner = email
    except Exception as e:
        printThis("((EXCEPTION))"+e)
        pass
    finally:
        return {'owner':owner, 'bindings':bindings}

def checkOwnerInherited(email,project_id):

    params = {
        'projectId': project_id,
        'body': {},
    }
    projAncestry = crm.projects().getAncestry(**params).execute()
    #{u'ancestor': [{u'resourceId': {u'type': u'project', u'id': u'clop1'}}, {u'resourceId': {u'type': u'organization', u'id': u'26877'}}]}

    printThis("porject "+project_id+" ancestry:")
    #printThis(str(projAncestry))

    for resource in projAncestry[u'ancestor'] :
        #printThis(str(resource))
        resType = resource[u'resourceId'][u'type']
        resId = resource[u'resourceId'][u'id']
        printThis(resId)
        if resType == 'project':
            continue
        if resType == 'organization':
            continue
        if resType == 'folder':
            getIAMFolder(resId)
    
    owner = None
    bindings = None

    return {'owner':owner, 'bindings':bindings}

def getprojects(email):
    # Get list of projects
    user_projects = {}
    output = []
    noorgprojects = {}
    request = crm.projects().list()

    global folder_ids

    # create a list to hold all the projects
    projects = []

    # page through the responses
    while request is not None:

        # execute the request
        response = request.execute()

        # add projects to the projects list
        if 'projects' in response:
            projects.extend(response['projects'])

        request = crm.projects().list_next(request, response)

    ##Find projects with no org to import
    # skip projects that are not active

    for p in sorted(projects, key=lambda x: x['name']):

        printThis("\nlooking at project "+p['projectId'])

        # skip projects that are not active
        if p['lifecycleState'] != 'ACTIVE':
            printThis("skipping "+p['projectId']+" cause it's not Active")
            continue

        # look for projects that have no parent
        if 'parent' not in p or not p['parent']:
            printThis("Found a project with no parent (but still have to check if the user has the Owner role):")
            printThis(p)
            project_id = p['projectId']

            checkOwnerResult = checkOwner(email,project_id)
            owner = checkOwnerResult['owner']

            # skip projects where the user is not the owner
            if not owner:
                printThis("--> User Doesn't have owner role!")
                continue

            printThis("--> User HAS owner role!")

            # create some text to output about the user's project
            text = '    * %s: %s [%s] (%s)' % (
                p['name'],
                p['projectId'],
                p['projectNumber'],
                p['lifecycleState'],
            )
            output.append(text)

            # # add bindings, google auth and owner to the project data
            p['bindings'] = checkOwnerResult['bindings']
            # p['google'] = g
            p['owner'] = email

            # add project to list of projects to import
            user_projects[project_id] = p
            inscopeprojects.update(user_projects)
        else:
            if ('parent' in p) :
                parentId=p['parent'][u'id']
                if (parentId not in folder_ids):
                    printThis("project " + p['name'] + " has parent in another org! Parent id: " + parentId + " . But checking to see if user has Owner role!")
                    
                    project_id = p['projectId']
                    
                    checkOwnerResult = checkOwner(email,project_id)
                    owner = checkOwnerResult['owner']
                    
                    if not owner and checkOwnerResult['bindings']:
                        #checkOwnerResult = checkOwnerInherited(email,project_id)
                        printThis("--> User Doesn't have owner role at Project Level, but It has getIAM on project - POSSIBLE it inherits Owner - adding it to possible list!")
                        projectsInOtherOrgsUnconfirmedRole.append(p['projectId'])
                        continue

                    # skip projects where the user is not the owner
                    if not owner:
                        printThis("--> User Doesn't have owner role and doesn't have getIAM on project -> impossible to inherit Owner from above!")
                        continue
                    printThis("--> User HAS owner role!\n")
                    projectsInOtherOrgsConfirmedOwner.append(p['projectId'])
                else:
                    printThis("project belongs to specified list of orgs/dirs, skipping")
    # display the output for this user
    # if output:
    #     print '  %s:' % (email)
    #     print '\n'.join(output)
    printThisImportant("\n\nFINAL REPORT FOR USER "+email)
    printThisImportant("==================================================================")
    if len(projectsInOtherOrgsConfirmedOwner) == 0:
        printThisImportant('*** No projects in other Orgs for ' + str(email))
    else :
        printThisImportant("*** " + str(len(projectsInOtherOrgsConfirmedOwner)) + " Projects in other Orgs with CONFIRMED Owner Role")
        printThisImportant(",".join(projectsInOtherOrgsConfirmedOwner))

    if len(projectsInOtherOrgsUnconfirmedRole) == 0:
        printThisImportant('*** No projects in other Orgs')
    else :
        printThisImportant("*** " + str(len(projectsInOtherOrgsUnconfirmedRole)) + " Projects in other Orgs with UNCONFIRMED Owner Role")
        printThisImportant(",".join(projectsInOtherOrgsUnconfirmedRole))

    if inscopeprojects == {}:
        printThisImportant('*** No legacy projects found')
        sys.exit(1)

    printThisImportant("*** " + str(len(inscopeprojects)) + " Legacy (No Parent) projects")
    printThisImportant(inscopeprojects)

def getIAMFolder(folderId):

    params = {
        'resource': "folders/"+folderId,
        'body': {},
    }

    folderIAMPolicy = None
    try:
        folderIAMPolicy = crm_v2beta1.folders().getIamPolicy(**params).execute()
    except Exception as e:#reason for exception: user does not have getIAMPolicy permission on the folder. Primitive Owner doesn't include getIAM on folder.
        printThis("((EXCEPTION))")
        printThis(e)
        pass
    finally:
        printThis("***Folder + " + folderId + " has IAM policy:")
        printThis(str(folderIAMPolicy))
        return folderIAMPolicy


def load_folder_ids(file_path):
    global folder_ids

    with open(file_path) as fp:
        line = fp.readline()
        printThis(file_path + " line="+line)
        ids = line.split(",")
        for i in ids:
            folder_ids.append(i)
        printThis("Now folder_ids=" + " ".join(folder_ids))

def printThisImportant(stringToPrint):
    printThis(stringToPrint, True)

def printThis(stringToPrint, important=False):
    if not verbose and not important:
        return
    print(stringToPrint)
        

def main():
    """Return the arguments from argparse."""
    legacyprojects = {}
    parser = argparse.ArgumentParser()
    parser.add_argument('--nofluff', action='store_true')
    parser.add_argument('--email')
    parser.add_argument('--service_account_json_filepath')
    parser.add_argument("--folderIDs_filenames", nargs='+')
    args = parser.parse_args()

    global verbose
    verbose=True
    if args.nofluff :
        print("No fluff specified - will only print summary")
        verbose = False

    global folder_ids
    folder_ids=[]

    #printThis("filenames:::")
    #printThis(",".join(args.folderIDs_filenames))

    for x in range(len(args.folderIDs_filenames)):
        printThis("importing file "+args.folderIDs_filenames[x])
        load_folder_ids(args.folderIDs_filenames[x])
    
    'Build API services using 2lo'
    buildapiservices(args.email, args.service_account_json_filepath)
    'Get projects with no org that user owns'
    getprojects(args.email)
    


if __name__ == "__main__":
    main()