res = ['NONE','NONE']
def fonc():
    global res
    rescopy = res.copy
    for re in rescopy:
        
        re='test'
    res = rescopy

fonc()
print(res)