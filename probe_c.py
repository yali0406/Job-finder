"""Temporary: guess a few more boards."""
from scanner.sources import ats
T=[("workday","akamai|wd1|External"),("workday","akamai|wd1|External_Careers"),("workday","akamai|wd1|akamaicareers"),
("workday","deltek|wd1|Deltek_Careers"),("workday","deltek|wd1|External"),("workday","deltek|wd5|Deltek"),
("workable","xapo"),("workable","xapo-bank"),("greenhouse","xapobank"),("lever","xapobank"),("ashby","xapo"),
("workable","safetywing"),("ashby","safety-wing"),("lever","safetywing"),("greenhouse","safetywing"),("breezy","safetywing")]
for a,s in T:
    try: j=ats.FETCHERS[a](s,"x")
    except Exception as e: j=None
    print("RESULT",a,s,None if j is None else len(j))
for u in ["https://www.akamai.com/careers","https://www.deltek.com/en/careers","https://www.xapobank.com/en/careers","https://safetywing.com/careers","https://www.bairesdev.com/join-us/"]:
    try: print("RESULT",u, ats.detect_from_careers(u,"x")[:2])
    except Exception as e: print("RESULT",u,"err",e)
