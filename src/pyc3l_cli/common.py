
import csv


def readCSV(file_path):
    header=[]
    data=[]

    with open(file_path) as csv_file:
        csv_reader = csv.reader(csv_file, delimiter=',')
        line_count = 0
        length=0
        for row in csv_reader:

            if line_count == 0:
                length=len(row)
                header=[item.replace('"','').strip() for item in row]
            else:
                if len(row)>length:
                    new_row=[]
                    in_str=False
                    for item in row:

                        if not in_str:
                            new_row.append(item)
                            if item.count('"')==1:
                                in_str=True
                        else:
                            new_row[-1]= new_row[-1] + ','+item
                            if item.count('"')==1:
                                    in_str=False
                    row=new_row

                row = [item.replace('"','').strip() for item in row]
                data.append(row)
            line_count += 1
    return header, data


