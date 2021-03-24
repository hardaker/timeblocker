#!/usr/bin/python3

from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter, FileType
import sys
import collections
import io
import matplotlib.dates as dates
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import pyfsdb

# set the default font size
matplotlib.rcParams.update({'font.size': 22})


def parse_args():
    "Parse the command line arguments."
    parser = ArgumentParser(formatter_class=ArgumentDefaultsHelpFormatter,
                            description=__doc__,
	                        epilog="Exmaple Usage: timeblocker.py input_file.fsdb output_file.png")

    parser.add_argument("-c", "--time-columns", default=['begin_time', 'end_time'],
                        type=str, nargs=2,
                        help="Start and stop column names to use")

    parser.add_argument("-p", "--positive-column", default=None, type=str,
                        help="The column to use for determining whether a square should be solid (if > 0) or or not (will always be solid if not used)")

    parser.add_argument("-t", "--time-step", default=86400, type=int,
                        help="Time step in seconds between blocks")

    parser.add_argument("-T", "--min-time-block", default=0, type=int,
                        help="Minimum number of open blocks between left/right blocks")

    parser.add_argument("-W", "--gap-width", type=float,
                        help="""The gap width that is removed from the block 
                        when drawn to ensure
                        some visible space occurs to the right.  With
                        a --min-time-blocks greater than 0, this
                        default value is 0 otherwise it will be
                        --time-step / 10.0 """)

    parser.add_argument("-B", "--block-height", default=.5, type=float,
                        help="The height block height")

    parser.add_argument("-F", "--output-fsdb", action="store_true",
                        help="Output as FSDB data")

    parser.add_argument("--test", action="store_true",
                        help="Run the test suite")

    parser.add_argument("input_file", type=FileType('r'),
                        nargs='?', default=sys.stdin,
                        help="file where time blocks are stored")

    parser.add_argument("output_file", type=str,
                        nargs="?", help="where to write the output image")

    args = parser.parse_args()

    if not args.gap_width:
        if args.min_time_block > 0:
            args.gap_width = 0
        else:
            args.gap_width = args.time_step / 10.0

    return args


def read_data(input_file_handle, columns, positives_column, time_step):
    fh = pyfsdb.Fsdb(file_handle=input_file_handle)
    column_numbers = fh.get_column_numbers(columns)
    positive_column = -1
    if positives_column:
        positive_column = fh.get_column_number(positives_column)
    data = []
    for row in fh:
        begin_time = int(float(row[column_numbers[0]]))
        begin_time = begin_time - begin_time % time_step

        end_time = float(row[column_numbers[1]])
        if (end_time % time_step) != 0:
            # jump to the next time_step looking forward
            end_time = end_time - (end_time % time_step) + time_step
        end_time = int(end_time)

        positives = 1
        if positive_column != -1:
            positives = row[positive_column]

        data.append([begin_time, end_time, positives])

    return data


# stores the number of times we saw something at this height
height_counts = collections.Counter()


def add_points(found_points, found_heights, output_chart, height_data):
    "collects found points and heights into the final chart"
    def key2(x):
        return x[1]

    # sort the results by reverse length (longest first) and add to the results
    found_points = sorted(found_points, key=key2, reverse=True)

    for point, h in zip(found_points, found_heights):
        height_data[h] = point[1]
        point.append(h)

    output_chart.extend(found_points)


def create_chart(data, timestep, min_time_block_offset=0):
    """Creates an series of output 'blocks' to print, with values of
    start_time, end_time, height.  Input data must be time-sorted by 
    start_time value (column 0).

    """
    output_chart = []    # list of ending times for a block
    height_data = {}     # timestamps of when a particular height ends
    last_time = 0
    minimum_time_offset = timestep * min_time_block_offset

    found_points = []  # [start_time, end_time]
    found_heights = []  # height of current
    height = 1

    # for each row of data, find a free block height for it
    for row in data:
        (begin_time, end_time, positives) = row

        # we found a new time-point, do clean up from the last
        if begin_time > last_time:
            # drop old used markers
            new_height_data = {}
            for value in height_data:
                if height_data[value] + minimum_time_offset > begin_time:
                    new_height_data[value] = height_data[value]
            height_data = new_height_data

            add_points(found_points, found_heights,
                       output_chart, height_data)

            found_points = []
            found_heights = []
            found_positives = []
            height = 0

        # find a vertical height at which there is no block in height_data
        height += 1
        while height in height_data:
            height += 1

        # remember this point in a list to add at the end of the time period
        found_points.append([begin_time, end_time, positives])
        found_heights.append(height)  # record the height it should be plotted at
        found_positives.append(positives)
        height_counts[height] += 1

        last_time = begin_time

    add_points(found_points, found_heights, output_chart, height_data)

    return output_chart


def output_to_fsdb(chart_data, output_file_name, column_names):
    """Writes the chart as a FSDB file with start, end, and height values"""
    outh = pyfsdb.Fsdb(out_file=output_file_name)
    outh.out_column_names = column_names + ['height']
    for row in chart_data:
        outh.append(row)
    outh.close()


def draw_chart(chart_data, out_file_name, gap_width=0, bar_height=.9):

    # Create figure and axes
    fig, ax = plt.subplots(1)

    # create rectangles
    max_height = 0
    max_time = 0

    face_colors = ['darkviolet', 'crimson']
    edge_colors = face_colors
    negative_colors = ['aqua', 'lime']

    heights_seen = collections.Counter()

    for row in chart_data:
        (start_time, end_time, positives, height) = row

        if height > max_height:
            max_height = height
        if end_time > max_time:
            max_time = end_time

        # refactor times into ones matplotlib can understand
        start_time = dates.epoch2num(start_time)
        time_width = dates.epoch2num(end_time - gap_width) - start_time

        heights_seen[height] += 1
        facecolor = None
        positives = int(positives)
        if positives > 0:
            facecolor = face_colors[heights_seen[height] % len(edge_colors)]
            edgecolor = edge_colors[heights_seen[height] % len(edge_colors)]
        else:
            facecolor = negative_colors[heights_seen[height] % len(negative_colors)]
            edgecolor = facecolor
        rect = patches.Rectangle((start_time, height),
                                 time_width, bar_height,
                                 edgecolor=edgecolor,
                                 facecolor=facecolor,
                                 linewidth=3)

        ax.add_patch(rect)

    # set the boundaries of the graph
    if gap_width == 0:
        gap_width = 1
    ax.set_xlim(dates.epoch2num(chart_data[0][0] - gap_width),
                dates.epoch2num(max_time + gap_width*2))
    ax.set_ylim(0 - bar_height * 1.5, max_height + bar_height*1.5 + 1)

    formatter = dates.DateFormatter("%Y/%m/%d")
    ax.xaxis.set_major_formatter(formatter)

    fig.autofmt_xdate()

    if out_file_name:
        fig.set_dpi(150)
        fig.set_size_inches(16, 16)
        plt.savefig(out_file_name, bbox_inches="tight", pad_inches=.1)
    else:
        plt.show()


def main():
    args = parse_args()

    if args.test:
        test_algorithm()
        sys.stderr.write("all tests passed\n")
        exit()

    data = read_data(args.input_file, args.time_columns,
                     args.positive_column, args.time_step)

    chart = create_chart(data, args.time_step,
                         min_time_block_offset=args.min_time_block)
    if args.output_fsdb:
        output_to_fsdb(chart, args.output_file)
    else:
        draw_chart(chart, args.output_file, args.gap_width, args.block_height)


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

    # add a minimum of a single block break between one block and the next
    minimum_spacing = 1
    input_data = [[4, 6],
                  [4, 8],
                  [6, 10],
                  [6, 8]]
    offset_expected_results = [[4, 6, 1],
                        [4, 8, 2],
                        [6, 10, 3],
                        [6, 8, 4]]
    results = create_chart(input_data, time_separator, min_time_block_offset=minimum_spacing)
    assert results == offset_expected_results

    # try again with deviations
    f_stream = io.StringIO("#fsdb -F t left right\n4.1\t5.5\n5.8\t7.9\n6\t8.1\n6\t6.9\n")
    input_data = read_data(f_stream, ['left', 'right'], time_separator)
    rounded_data = [[4, 6],
                    [4, 8],
                    [6, 10],
                    [6, 8]]
    assert input_data == rounded_data

    results = create_chart(input_data, time_separator)
    assert results == expected_results


if __name__ == "__main__":
    main()
