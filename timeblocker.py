#!/usr/bin/python3

from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter, FileType
import sys

def parse_args():
    "Parse the command line arguments."
    parser = ArgumentParser(formatter_class=ArgumentDefaultsHelpFormatter,
                            description=__doc__,
	                        epilog="Exmaple Usage: timeblocker.py input_file.fsdb output_file.png")

    parser.add_argument("-c", "--time-columns", default=['begin_time', 'end_time'],
                        type=str, nargs=2,
                        help="Start and stop column names to use")

    parser.add_argument("-t", "--time-step", default=86400, type=int,
                        help="Time step in seconds between blocks")

    parser.add_argument("-F", "--output-fsdb", action="store_true",
                        help="Output as FSDB data")

    parser.add_argument("input_file", type=FileType('r'),
                        nargs='?', default=sys.stdin,
                        help="file where time blocks are stored")

    parser.add_argument("output_file", type=str,
                        nargs=1, help="where to write the output image")

    args = parser.parse_args()
    return args


def read_data(input_file_handle, columns):
    import pyfsdb
    fh = pyfsdb.Fsdb(file_handle=input_file_handle)
    column_numbers = fh.get_column_numbers(columns)
    data = []
    for row in fh:
        data.append([int(row[column_numbers[0]]), int(row[column_numbers[1]])])

    return data


def create_chart(data, timestep):
    """Creates an series of output 'blocks' to print, with values of
    start_time, end_time, height.  Input data must be time-sorted by 
    start_time value (column 0).
    """
    output_chart = []
    # list of ending times for a block
    height_data = {}
    initial_time = data[0][0]
    last_time = 0

    # for each row of data, find a free block height for it
    for row in data:
        (begin_time, end_time) = row

        # drop old used markers
        if begin_time > last_time:
            new_height_data = {}
            for value in height_data:
                if height_data[value] > begin_time:
                    new_height_data[value] = height_data[value]
            height_data = new_height_data

        # find a vertical height at which there is no block in height_data
        height = 1
        while height in height_data:
            height += 1

        # mark this height as now unusable for a while
        height_data[height] = end_time

        # save the results
        output_chart.append([begin_time, end_time, height])

        last_time = begin_time

    return output_chart


def output_to_fsdb(chart_data, output_file_name, column_names):
    """Writes the chart as a FSDB file with start, end, and height values"""
    import pyfsdb
    outh = pyfsdb.Fsdb(out_file=output_file_name)
    outh.out_column_names = column_names + ['height']
    for row in chart_data:
        outh.append(row)
    outh.close()


def draw_chart(chart_data, out_file_name, gap_width=0):
    import matplotlib.pyplot as plt
    import matplotlib.patches as patches

    # Create figure and axes
    fig,ax = plt.subplots(1)

    # create rectangles
    max_height = 0
    max_time = 0
    for row in chart_data:
        (start_time, end_time, height) = row
        rect = patches.Rectangle((start_time, height),
                                 end_time - gap_width, 1, # height = 1,
                                 edgecolor='r', facecolor='k', linewidth=11)
        if height > max_height:
            max_height = height
        if end_time > max_time:
            max_time = end_time
        ax.add_patch(rect)

    import pdb ; pdb.set_trace()
    ax.set_xlim(chart_data[0][0], 2*end_time + gap_width)
    ax.set_ylim(0, max_height+1)

    plt.show()



def main():
    args = parse_args()

    data = read_data(args.input_file, args.time_columns)
    chart = create_chart(data, args.time_step)
    if args.output_fsdb:
        output_to_fsdb(chart, args.output_file)
    else:
        draw_chart(chart, args.output_file, args.time_step / 2)


def test_algorithm():
    time_separator = 2
    input_data = [[4, 6],
                  [4, 8],
                  [6, 10],
                  [6, 8]]
    expected_results = [[4, 6, 1],
                        [4, 8, 2],
                        [6, 10, 1],
                        [6, 8, 3]]
    results = create_chart(input_data, time_separator)
    assert results == expected_results


if __name__ == "__main__":
    test_algorithm()
    main()
