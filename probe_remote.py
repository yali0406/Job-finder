"""Temporary: test the new fetchers."""
from scanner.sources import ats
T=[("Atlassian","atlassian","x"),("DocuSign","jibe","https://careers.docusign.com"),("McGraw Hill","jibe","https://careers.mheducation.com"),
("Workiva","workday","workiva|wd503|careers"),("Cengage","workday","cengage|wd5|CengageEMEACareers"),("Cengage NA","workday","cengage|wd5|CengageNorthAmericaCareers"),
("Sorcero","greenhouse","sorcero"),("Fivetran","greenhouse","fivetran"),("Zero Hash","breezy","zero-hash"),("Runway","ashby","runway-ml")]
for n,a,s in T:
    try:
        j=ats.FETCHERS[a](s,n)
    except Exception as e:
        print("RESULT",n,"ERR",e); continue
    print("RESULT",n,None if j is None else len(j), [(x.title,x.location,x.url[:80]) for x in (j or [])[:3]])
